import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.balance.models import BalanceCache, LedgerEntry
from app.domain.settlement.models import Settlement
from app.repositories.base import BaseRepository


class BalanceCacheRepository(BaseRepository[BalanceCache]):
    model = BalanceCache

    async def get_pair(
        self, group_id: uuid.UUID, user_id: uuid.UUID, other_user_id: uuid.UUID
    ) -> BalanceCache | None:
        return await self.db.scalar(
            select(BalanceCache).where(
                BalanceCache.group_id == group_id,
                BalanceCache.user_id == user_id,
                BalanceCache.other_user_id == other_user_id,
            )
        )

    async def get_group_balances(self, group_id: uuid.UUID) -> list[BalanceCache]:
        result = await self.db.scalars(
            select(BalanceCache).where(BalanceCache.group_id == group_id)
        )
        return list(result.all())

    async def get_user_balances_all_groups(self, user_id: uuid.UUID) -> list[BalanceCache]:
        result = await self.db.scalars(
            select(BalanceCache).where(BalanceCache.user_id == user_id)
        )
        return list(result.all())

    async def upsert(
        self,
        group_id: uuid.UUID,
        user_id: uuid.UUID,
        other_user_id: uuid.UUID,
        delta: Decimal,
    ) -> None:
        """Atomically add delta to the cached balance, creating row if absent."""
        row = await self.get_pair(group_id, user_id, other_user_id)
        if row:
            row.balance_amount = Decimal(str(row.balance_amount)) + delta
        else:
            self.db.add(
                BalanceCache(
                    group_id=group_id,
                    user_id=user_id,
                    other_user_id=other_user_id,
                    balance_amount=delta,
                )
            )
        await self.db.flush()


class LedgerRepository(BaseRepository[LedgerEntry]):
    model = LedgerEntry

    async def get_group_entries(self, group_id: uuid.UUID) -> list[LedgerEntry]:
        result = await self.db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.group_id == group_id)
            .order_by(LedgerEntry.created_at)
        )
        return list(result.all())


class SettlementRepository(BaseRepository[Settlement]):
    model = Settlement

    async def get_group_settlements(self, group_id: uuid.UUID) -> list[Settlement]:
        result = await self.db.scalars(
            select(Settlement)
            .where(Settlement.group_id == group_id)
            .order_by(Settlement.created_at.desc())
        )
        return list(result.all())
