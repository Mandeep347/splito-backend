import uuid
from decimal import Decimal
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ExpenseNotFoundError,
    UnauthorizedError,
    UserNotInGroupError,
)
from app.domain.balance.models import LedgerEntry
from app.domain.expense.models import Expense, ExpenseParticipant, ExpenseStatus
from app.domain.group.models import MemberStatus
from app.domain.user.models import User
from app.repositories.expense_repository import ExpenseRepository
from app.repositories.group_repository import GroupMemberRepository, GroupRepository
from app.schemas.expense import (
    CreateExpenseRequest,
    ExpenseResponse,
    PaginatedExpenses,
    ParticipantResponse,
    UpdateExpenseRequest,
)
from app.services.balance_service import BalanceService
from app.services.split_service import get_split_strategy


def _to_expense_response(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        group_id=expense.group_id,
        paid_by_user_id=expense.paid_by_user_id,
        paid_by_name=expense.paid_by.name if expense.paid_by else "Unknown",
        title=expense.title,
        description=expense.description,
        total_amount=Decimal(str(expense.total_amount)),
        currency=expense.currency,
        split_type=expense.split_type,
        status=expense.status,
        created_at=expense.created_at,
        participants=[
            ParticipantResponse(
                user_id=p.user_id,
                name=p.user.name if p.user else "Unknown",
                owed_amount=Decimal(str(p.owed_amount)),
                percentage=Decimal(str(p.percentage)) if p.percentage else None,
                shares=p.shares,
            )
            for p in expense.participants
        ],
    )


class ExpenseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.expense_repo = ExpenseRepository(db)
        self.group_repo = GroupRepository(db)
        self.member_repo = GroupMemberRepository(db)
        self.balance_svc = BalanceService(db)

    async def create_expense(
        self,
        group_id: uuid.UUID,
        payload: CreateExpenseRequest,
        requester: User,
    ) -> ExpenseResponse:
        # Guard: requester must be active member
        await self._require_active_member(group_id, requester.id)

        # Guard: payer must be active member
        await self._require_active_member(group_id, payload.paid_by_user_id)

        # Compute split
        strategy = get_split_strategy(payload.split_type)
        splits = strategy.compute(payload.total_amount, payload)

        # Guard: all participants must be active members
        all_member_ids = {
            m.user_id
            for m in await self.member_repo.get_active_members(group_id)
        }
        for s in splits:
            if s.user_id not in all_member_ids:
                raise UserNotInGroupError(
                    f"Participant {s.user_id} is not an active member of this group."
                )

        # ── Atomic write: expense + participants + ledger entries + balance cache ──
        expense = Expense(
            group_id=group_id,
            paid_by_user_id=payload.paid_by_user_id,
            title=payload.title,
            description=payload.description,
            total_amount=payload.total_amount,
            currency=payload.currency.upper(),
            split_type=payload.split_type,
            status=ExpenseStatus.ACTIVE,
        )
        self.db.add(expense)
        await self.db.flush()

        # Participants
        for s in splits:
            self.db.add(ExpenseParticipant(
                expense_id=expense.id,
                user_id=s.user_id,
                owed_amount=s.owed_amount,
                percentage=s.percentage,
                shares=s.shares,
            ))

        # Ledger entries (one per debtor→payer pair)
        debts: list[tuple[uuid.UUID, Decimal]] = []
        for s in splits:
            if s.user_id != payload.paid_by_user_id:
                self.db.add(LedgerEntry(
                    group_id=group_id,
                    entry_type="EXPENSE_CREATED",
                    source_id=expense.id,
                    from_user_id=s.user_id,
                    to_user_id=payload.paid_by_user_id,
                    amount=s.owed_amount,
                    currency=payload.currency.upper(),
                ))
                debts.append((s.user_id, s.owed_amount))

        await self.db.flush()

        # Update balance cache
        await self.balance_svc.apply_expense(
            group_id, payload.paid_by_user_id, debts, payload.currency.upper()
        )

        expense = await self.expense_repo.get_by_id_with_participants(expense.id)
        return _to_expense_response(expense)  # type: ignore

    async def get_group_expenses(
        self,
        group_id: uuid.UUID,
        requester: User,
        page: int = 1,
        limit: int = 20,
    ) -> PaginatedExpenses:
        await self._require_active_member(group_id, requester.id)
        expenses, total = await self.expense_repo.get_group_expenses_paginated(
            group_id, page, limit
        )
        return PaginatedExpenses(
            items=[_to_expense_response(e) for e in expenses],
            page=page,
            limit=limit,
            total_items=total,
            total_pages=ceil(total / limit) if total else 0,
        )

    async def get_expense(
        self, expense_id: uuid.UUID, requester: User
    ) -> ExpenseResponse:
        expense = await self.expense_repo.get_by_id_with_participants(expense_id)
        if not expense or expense.status == ExpenseStatus.REVERSED:
            raise ExpenseNotFoundError(f"Expense {expense_id} not found.")
        await self._require_active_member(expense.group_id, requester.id)
        return _to_expense_response(expense)

    async def update_expense(
        self,
        expense_id: uuid.UUID,
        payload: UpdateExpenseRequest,
        requester: User,
    ) -> ExpenseResponse:
        expense = await self.expense_repo.get_by_id_with_participants(expense_id)
        if not expense or expense.status != ExpenseStatus.ACTIVE:
            raise ExpenseNotFoundError(f"Expense {expense_id} not found.")
        await self._require_active_member(expense.group_id, requester.id)

        if payload.title is not None:
            expense.title = payload.title
        if payload.description is not None:
            expense.description = payload.description
        await self.db.flush()

        expense = await self.expense_repo.get_by_id_with_participants(expense_id)
        return _to_expense_response(expense)  # type: ignore

    async def reverse_expense(
        self,
        expense_id: uuid.UUID,
        requester: User,
    ) -> ExpenseResponse:
        """
        Soft-delete: marks expense as REVERSED and undoes balance impact.
        Business Rule: never hard-delete financial records.
        """
        expense = await self.expense_repo.get_by_id_with_participants(expense_id)
        if not expense or expense.status != ExpenseStatus.ACTIVE:
            raise ExpenseNotFoundError(f"Expense {expense_id} not found.")
        await self._require_active_member(expense.group_id, requester.id)

        # Undo balance cache
        debts = [
            (p.user_id, Decimal(str(p.owed_amount)))
            for p in expense.participants
            if p.user_id != expense.paid_by_user_id
        ]
        await self.balance_svc.reverse_expense(
            expense.group_id, expense.paid_by_user_id, debts
        )

        # Ledger entry for audit trail
        for p in expense.participants:
            if p.user_id != expense.paid_by_user_id:
                self.db.add(LedgerEntry(
                    group_id=expense.group_id,
                    entry_type="EXPENSE_REVERSED",
                    source_id=expense.id,
                    from_user_id=p.user_id,
                    to_user_id=expense.paid_by_user_id,
                    amount=Decimal(str(p.owed_amount)),
                    currency=expense.currency,
                ))

        expense.status = ExpenseStatus.REVERSED
        await self.db.flush()

        expense = await self.expense_repo.get_by_id_with_participants(expense_id)
        return _to_expense_response(expense)  # type: ignore

    # ── Guard ─────────────────────────────────────────────────────────────────

    async def _require_active_member(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        membership = await self.member_repo.get_active_membership(group_id, user_id)
        if not membership:
            raise UserNotInGroupError(
                f"User {user_id} is not an active member of group {group_id}."
            )
