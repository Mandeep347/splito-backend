import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base

if TYPE_CHECKING:
    from app.domain.group.models import Group
    from app.domain.user.models import User


class SplitType:
    EQUAL = "EQUAL"
    EXACT = "EXACT"
    PERCENTAGE = "PERCENTAGE"
    SHARE = "SHARE"


class ExpenseStatus:
    ACTIVE = "ACTIVE"
    REVERSED = "REVERSED"
    SETTLED = "SETTLED"


class Expense(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("total_amount > 0", name="ck_expense_positive_amount"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    paid_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    split_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ExpenseStatus.ACTIVE, nullable=False)

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="expenses")
    paid_by: Mapped["User"] = relationship("User", foreign_keys=[paid_by_user_id])
    participants: Mapped[list["ExpenseParticipant"]] = relationship(
        "ExpenseParticipant",
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Expense id={self.id} title={self.title} amount={self.total_amount}>"


class ExpenseParticipant(Base, UUIDMixin):
    __tablename__ = "expense_participants"
    __table_args__ = (
        CheckConstraint("owed_amount >= 0", name="ck_participant_non_negative"),
    )

    expense_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    owed_amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    percentage: Mapped[object | None] = mapped_column(Numeric(5, 2), nullable=True)
    shares: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    expense: Mapped["Expense"] = relationship("Expense", back_populates="participants")
    user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ExpenseParticipant expense={self.expense_id} user={self.user_id} owed={self.owed_amount}>"
