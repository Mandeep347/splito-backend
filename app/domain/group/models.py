import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import TimestampMixin, UUIDMixin
from app.db.session import Base

if TYPE_CHECKING:
    from app.domain.user.models import User
    from app.domain.expense.models import Expense
    from app.domain.settlement.models import Settlement


class GroupStatus:
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    CLOSED = "CLOSED"


class MemberRole:
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class MemberStatus:
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    LEFT = "LEFT"
    REMOVED = "REMOVED"
    BLOCKED = "BLOCKED"


class Group(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "groups"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    default_currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=GroupStatus.ACTIVE, nullable=False)

    # Relationships
    members: Mapped[list["GroupMember"]] = relationship(
        "GroupMember", back_populates="group", lazy="selectin"
    )
    expenses: Mapped[list["Expense"]] = relationship(
        "Expense", back_populates="group", lazy="select"
    )
    settlements: Mapped[list["Settlement"]] = relationship(
        "Settlement", back_populates="group", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Group id={self.id} name={self.name}>"


class GroupMember(Base, UUIDMixin):
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_member"),)

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), default=MemberRole.MEMBER, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=MemberStatus.ACTIVE, nullable=False)

    from sqlalchemy import DateTime, func
    joined_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    group: Mapped["Group"] = relationship("Group", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<GroupMember group={self.group_id} user={self.user_id}>"
