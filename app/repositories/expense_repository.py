import uuid
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.expense.models import Expense, ExpenseParticipant, ExpenseStatus
from app.repositories.base import BaseRepository


class ExpenseRepository(BaseRepository[Expense]):
    model = Expense

    async def get_by_id_with_participants(self, expense_id: uuid.UUID) -> Expense | None:
        return await self.db.scalar(
            select(Expense)
            .where(Expense.id == expense_id)
            .options(
                selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
                selectinload(Expense.paid_by),
            )
        )

    async def get_group_expenses_paginated(
        self,
        group_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        status: str = ExpenseStatus.ACTIVE,
    ) -> tuple[list[Expense], int]:
        """Returns (expenses, total_count)."""
        base_query = (
            select(Expense)
            .where(Expense.group_id == group_id, Expense.status == status)
            .options(
                selectinload(Expense.participants).selectinload(ExpenseParticipant.user),
                selectinload(Expense.paid_by),
            )
            .order_by(Expense.created_at.desc())
        )

        total = await self.db.scalar(
            select(func.count()).select_from(
                select(Expense.id)
                .where(Expense.group_id == group_id, Expense.status == status)
                .subquery()
            )
        )
        total = total or 0

        expenses = await self.db.scalars(
            base_query.offset((page - 1) * limit).limit(limit)
        )
        return list(expenses.all()), total

    async def get_group_expenses_active(self, group_id: uuid.UUID) -> list[Expense]:
        """All active expenses for balance computation."""
        result = await self.db.scalars(
            select(Expense)
            .where(Expense.group_id == group_id, Expense.status == ExpenseStatus.ACTIVE)
            .options(selectinload(Expense.participants))
        )
        return list(result.all())


class ExpenseParticipantRepository(BaseRepository[ExpenseParticipant]):
    model = ExpenseParticipant

    async def get_user_expenses_in_group(
        self, group_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[ExpenseParticipant]:
        result = await self.db.scalars(
            select(ExpenseParticipant)
            .join(Expense, Expense.id == ExpenseParticipant.expense_id)
            .where(
                Expense.group_id == group_id,
                ExpenseParticipant.user_id == user_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
        )
        return list(result.all())
