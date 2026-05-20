import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    SelfSettlementError,
    SettlementExceedsBalanceError,
    SettlementNotFoundError,
    UserNotInGroupError,
)
from app.domain.balance.models import LedgerEntry
from app.domain.settlement.models import Settlement
from app.domain.user.models import User
from app.repositories.balance_repository import BalanceCacheRepository, SettlementRepository
from app.repositories.group_repository import GroupMemberRepository
from app.schemas.balance import CreateSettlementRequest, SettlementResponse
from app.services.balance_service import BalanceService


def _to_settlement_response(s: Settlement, from_name: str, to_name: str) -> SettlementResponse:
    return SettlementResponse(
        id=s.id,
        group_id=s.group_id,
        from_user_id=s.from_user_id,
        from_user_name=from_name,
        to_user_id=s.to_user_id,
        to_user_name=to_name,
        amount=Decimal(str(s.amount)),
        currency=s.currency,
        note=s.note,
        status=s.status,
        created_at=s.created_at,
    )


class SettlementService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settlement_repo = SettlementRepository(db)
        self.member_repo = GroupMemberRepository(db)
        self.balance_repo = BalanceCacheRepository(db)
        self.balance_svc = BalanceService(db)

    async def create_settlement(
        self,
        group_id: uuid.UUID,
        payload: CreateSettlementRequest,
        requester: User,
    ) -> SettlementResponse:
        # Business Rule: no self-settlement
        if payload.from_user_id == payload.to_user_id:
            raise SelfSettlementError("Cannot settle with yourself.")

        # Both users must be group members
        for uid in (payload.from_user_id, payload.to_user_id):
            if not await self.member_repo.get_active_membership(group_id, uid):
                raise UserNotInGroupError(f"User {uid} is not an active member of this group.")

        # Business Rule: settlement cannot exceed outstanding balance
        balance_row = await self.balance_repo.get_pair(
            group_id, payload.from_user_id, payload.to_user_id
        )
        outstanding = Decimal(str(balance_row.balance_amount)) if balance_row else Decimal("0")

        if outstanding <= Decimal("0"):
            raise SettlementExceedsBalanceError(
                f"{payload.from_user_id} does not owe {payload.to_user_id} anything in this group."
            )
        if payload.amount > outstanding:
            raise SettlementExceedsBalanceError(
                f"Settlement amount {payload.amount} exceeds outstanding balance {outstanding}."
            )

        # Fetch names for response
        from_user = await self.db.scalar(select(User).where(User.id == payload.from_user_id))
        to_user = await self.db.scalar(select(User).where(User.id == payload.to_user_id))

        # Create settlement record
        settlement = Settlement(
            group_id=group_id,
            from_user_id=payload.from_user_id,
            to_user_id=payload.to_user_id,
            amount=payload.amount,
            currency=payload.currency.upper(),
            note=payload.note,
            status="COMPLETED",
        )
        self.db.add(settlement)
        await self.db.flush()

        # Immutable ledger entry
        self.db.add(LedgerEntry(
            group_id=group_id,
            entry_type="SETTLEMENT_RECORDED",
            source_id=settlement.id,
            from_user_id=payload.from_user_id,
            to_user_id=payload.to_user_id,
            amount=payload.amount,
            currency=payload.currency.upper(),
        ))

        # Update balance cache
        await self.balance_svc.apply_settlement(
            group_id, payload.from_user_id, payload.to_user_id, payload.amount
        )

        return _to_settlement_response(
            settlement,
            from_name=from_user.name if from_user else "Unknown",
            to_name=to_user.name if to_user else "Unknown",
        )

    async def get_group_settlements(
        self, group_id: uuid.UUID, requester: User
    ) -> list[SettlementResponse]:
        if not await self.member_repo.get_active_membership(group_id, requester.id):
            raise UserNotInGroupError("You are not a member of this group.")

        settlements = await self.settlement_repo.get_group_settlements(group_id)
        result = []
        for s in settlements:
            from_user = await self.db.scalar(select(User).where(User.id == s.from_user_id))
            to_user = await self.db.scalar(select(User).where(User.id == s.to_user_id))
            result.append(_to_settlement_response(
                s,
                from_name=from_user.name if from_user else "Unknown",
                to_name=to_user.name if to_user else "Unknown",
            ))
        return result
