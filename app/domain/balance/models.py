import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base


class LedgerEntry(Base, UUIDMixin, TimestampMixin):
    """
    Immutable financial ledger.
    Every expense creation, reversal and settlement writes a row here.
    Source of truth for audit and balance recomputation.
    """
    __tablename__ = "ledger_entries"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)  # EXPENSE_CREATED, SETTLEMENT, EXPENSE_REVERSED
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)  # expense_id or settlement_id
    from_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    def __repr__(self) -> str:
        return f"<LedgerEntry type={self.entry_type} amount={self.amount}>"


class BalanceCache(Base, UUIDMixin):
    """
    Materialized pairwise balance for fast reads.
    NOT the source of truth — always recomputable from ledger_entries.
    Convention: positive = user_id owes other_user_id.
    """
    __tablename__ = "balances_cache"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", "other_user_id", name="uq_balance_pair"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    other_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    balance_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)

    from sqlalchemy import DateTime, func
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<BalanceCache {self.user_id} → {self.other_user_id} = {self.balance_amount}>"
