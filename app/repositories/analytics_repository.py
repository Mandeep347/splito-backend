"""
Analytics repository.
All computation happens in PostgreSQL — no Python-side aggregation loops.
Every query returns exactly what the service layer needs; nothing more.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Integer, Numeric, case, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.balance.models import BalanceCache
from app.domain.expense.models import Expense, ExpenseParticipant, ExpenseStatus
from app.domain.group.models import Group, GroupMember, GroupStatus, MemberStatus
from app.domain.settlement.models import Settlement
from app.domain.user.models import User


class AnalyticsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Group helpers ─────────────────────────────────────────────────────────

    async def get_group_total_expenses(self, group_id: uuid.UUID) -> tuple[Decimal, int]:
        """Returns (total_amount, expense_count) for active expenses in group."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Expense.total_amount), 0).label("total"),
                func.count(Expense.id).label("count"),
            ).where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
        )
        row = result.one()
        return Decimal(str(row.total)), int(row.count)

    async def get_group_total_settlements(self, group_id: uuid.UUID) -> Decimal:
        """Returns total settlement amount for a group."""
        result = await self.db.scalar(
            select(func.coalesce(func.sum(Settlement.amount), 0)).where(
                Settlement.group_id == group_id
            )
        )
        return Decimal(str(result))

    async def get_group_largest_expense(
        self, group_id: uuid.UUID
    ) -> tuple[Decimal, str | None]:
        """Returns (largest_amount, title) or (0, None)."""
        result = await self.db.execute(
            select(Expense.total_amount, Expense.title)
            .where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
            .order_by(Expense.total_amount.desc())
            .limit(1)
        )
        row = result.first()
        if not row:
            return Decimal("0"), None
        return Decimal(str(row.total_amount)), row.title

    async def get_group_average_expense(self, group_id: uuid.UUID) -> Decimal:
        """Returns average expense amount for a group."""
        result = await self.db.scalar(
            select(func.coalesce(func.avg(Expense.total_amount), 0)).where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
        )
        return Decimal(str(result)).quantize(Decimal("0.01"))

    async def get_member_spending_breakdown(
        self, group_id: uuid.UUID
    ) -> list[dict]:
        """
        Per-member breakdown:
          - total_paid:  sum of expenses where paid_by = member
          - total_owed:  sum of owed_amount from expense_participants
          - expense_count: how many expenses they paid for

        Single query joining users, group_members, expenses, expense_participants.
        """
        # Total paid per member (payer perspective)
        paid_subq = (
            select(
                Expense.paid_by_user_id.label("user_id"),
                func.coalesce(func.sum(Expense.total_amount), 0).label("total_paid"),
                func.count(Expense.id).label("expense_count"),
            )
            .where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
            .group_by(Expense.paid_by_user_id)
            .subquery()
        )

        # Total owed per member (participant perspective)
        owed_subq = (
            select(
                ExpenseParticipant.user_id.label("user_id"),
                func.coalesce(
                    func.sum(ExpenseParticipant.owed_amount), 0
                ).label("total_owed"),
            )
            .join(Expense, Expense.id == ExpenseParticipant.expense_id)
            .where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
            .group_by(ExpenseParticipant.user_id)
            .subquery()
        )

        # Net balance from cache (positive = member owes others)
        balance_subq = (
            select(
                BalanceCache.user_id.label("user_id"),
                func.coalesce(func.sum(BalanceCache.balance_amount), 0).label(
                    "net_balance_raw"
                ),
            )
            .where(BalanceCache.group_id == group_id)
            .group_by(BalanceCache.user_id)
            .subquery()
        )

        stmt = (
            select(
                User.id.label("user_id"),
                User.name.label("name"),
                func.coalesce(paid_subq.c.total_paid, 0).label("total_paid"),
                func.coalesce(owed_subq.c.total_owed, 0).label("total_owed"),
                func.coalesce(paid_subq.c.expense_count, 0).label("expense_count"),
                func.coalesce(balance_subq.c.net_balance_raw, 0).label(
                    "net_balance_raw"
                ),
            )
            .join(GroupMember, GroupMember.user_id == User.id)
            .outerjoin(paid_subq, paid_subq.c.user_id == User.id)
            .outerjoin(owed_subq, owed_subq.c.user_id == User.id)
            .outerjoin(balance_subq, balance_subq.c.user_id == User.id)
            .where(
                GroupMember.group_id == group_id,
                GroupMember.status == MemberStatus.ACTIVE,
            )
            .order_by(func.coalesce(paid_subq.c.total_paid, 0).desc())
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "name": row.name,
                "total_paid": Decimal(str(row.total_paid)),
                "total_owed": Decimal(str(row.total_owed)),
                "expense_count": int(row.expense_count),
                # net_balance: negative raw = this user is owed (creditor)
                # flip sign so positive = creditor (UI-friendly)
                "net_balance": -Decimal(str(row.net_balance_raw)),
            }
            for row in rows
        ]

    async def get_group_monthly_spending(
        self, group_id: uuid.UUID, months: int = 12
    ) -> list[dict]:
        """
        Monthly spending totals for the last N months.
        Returns rows ordered oldest → newest.
        """
        stmt = (
            select(
                func.extract("year", Expense.created_at).cast(Integer).label("year"),
                func.extract("month", Expense.created_at).cast(Integer).label("month"),
                func.coalesce(func.sum(Expense.total_amount), 0).label("total_amount"),
                func.count(Expense.id).label("expense_count"),
            )
            .where(
                Expense.group_id == group_id,
                Expense.status == ExpenseStatus.ACTIVE,
                Expense.created_at
                >= func.date_trunc(
                    "month",
                    func.now() - text(f"interval '{months - 1} months'"),
                ),
            )
            .group_by(
                func.extract("year", Expense.created_at),
                func.extract("month", Expense.created_at),
            )
            .order_by(
                func.extract("year", Expense.created_at),
                func.extract("month", Expense.created_at),
            )
        )
        result = await self.db.execute(stmt)
        return [
            {
                "year": row.year,
                "month": row.month,
                "total_amount": Decimal(str(row.total_amount)),
                "expense_count": int(row.expense_count),
            }
            for row in result.all()
        ]

    # ── User helpers ──────────────────────────────────────────────────────────

    async def get_user_total_paid_all_groups(self, user_id: uuid.UUID) -> tuple[Decimal, int]:
        """Total amount paid and expense count across all groups."""
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Expense.total_amount), 0).label("total"),
                func.count(Expense.id).label("count"),
            ).where(
                Expense.paid_by_user_id == user_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
        )
        row = result.one()
        return Decimal(str(row.total)), int(row.count)

    async def get_user_balance_totals(
        self, user_id: uuid.UUID
    ) -> tuple[Decimal, Decimal]:
        """
        Returns (total_owed_to_others, total_others_owe_user).
        From balance_cache: positive = user owes other, negative = other owes user.
        """
        result = await self.db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (BalanceCache.balance_amount > 0, BalanceCache.balance_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("owed_to_others"),
                func.coalesce(
                    func.sum(
                        case(
                            (BalanceCache.balance_amount < 0, -BalanceCache.balance_amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("others_owe_user"),
            ).where(BalanceCache.user_id == user_id)
        )
        row = result.one()
        return Decimal(str(row.owed_to_others)), Decimal(str(row.others_owe_user))

    async def get_user_group_breakdown(self, user_id: uuid.UUID) -> list[dict]:
        """
        Per-group spending summary for a user.
        Returns groups ordered by total_spent desc.
        """
        # Amount this user paid per group
        paid_subq = (
            select(
                Expense.group_id.label("group_id"),
                func.coalesce(func.sum(Expense.total_amount), 0).label("user_paid"),
                func.count(Expense.id).label("expense_count"),
            )
            .where(
                Expense.paid_by_user_id == user_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
            .group_by(Expense.group_id)
            .subquery()
        )

        # Amount this user owes per group
        owed_subq = (
            select(
                Expense.group_id.label("group_id"),
                func.coalesce(
                    func.sum(ExpenseParticipant.owed_amount), 0
                ).label("user_owed"),
            )
            .join(
                ExpenseParticipant, ExpenseParticipant.expense_id == Expense.id
            )
            .where(
                ExpenseParticipant.user_id == user_id,
                Expense.status == ExpenseStatus.ACTIVE,
            )
            .group_by(Expense.group_id)
            .subquery()
        )

        # Total expense amount per group (all members)
        total_subq = (
            select(
                Expense.group_id.label("group_id"),
                func.coalesce(func.sum(Expense.total_amount), 0).label(
                    "total_spent"
                ),
            )
            .where(Expense.status == ExpenseStatus.ACTIVE)
            .group_by(Expense.group_id)
            .subquery()
        )

        stmt = (
            select(
                Group.id.label("group_id"),
                Group.name.label("group_name"),
                Group.default_currency.label("currency"),
                func.coalesce(paid_subq.c.user_paid, 0).label("user_paid"),
                func.coalesce(owed_subq.c.user_owed, 0).label("user_owed"),
                func.coalesce(total_subq.c.total_spent, 0).label("total_spent"),
                func.coalesce(paid_subq.c.expense_count, 0).label("expense_count"),
            )
            .join(GroupMember, GroupMember.group_id == Group.id)
            .outerjoin(paid_subq, paid_subq.c.group_id == Group.id)
            .outerjoin(owed_subq, owed_subq.c.group_id == Group.id)
            .outerjoin(total_subq, total_subq.c.group_id == Group.id)
            .where(
                GroupMember.user_id == user_id,
                GroupMember.status == MemberStatus.ACTIVE,
                Group.status == GroupStatus.ACTIVE,
            )
            .order_by(func.coalesce(total_subq.c.total_spent, 0).desc())
        )

        result = await self.db.execute(stmt)
        return [
            {
                "group_id": row.group_id,
                "group_name": row.group_name,
                "currency": row.currency,
                "user_paid": Decimal(str(row.user_paid)),
                "user_owed": Decimal(str(row.user_owed)),
                "total_spent": Decimal(str(row.total_spent)),
                "expense_count": int(row.expense_count),
            }
            for row in result.all()
        ]

    async def get_user_monthly_spending(
        self, user_id: uuid.UUID, months: int = 12
    ) -> list[dict]:
        """
        Monthly totals of expenses PAID BY this user across all groups.
        Ordered oldest → newest.
        """
        stmt = (
            select(
                func.extract("year", Expense.created_at).cast(Integer).label("year"),
                func.extract("month", Expense.created_at).cast(Integer).label("month"),
                func.coalesce(func.sum(Expense.total_amount), 0).label("total_amount"),
                func.count(Expense.id).label("expense_count"),
            )
            .where(
                Expense.paid_by_user_id == user_id,
                Expense.status == ExpenseStatus.ACTIVE,
                Expense.created_at
                >= func.date_trunc(
                    "month",
                    func.now() - text(f"interval '{months - 1} months'"),
                ),
            )
            .group_by(
                func.extract("year", Expense.created_at),
                func.extract("month", Expense.created_at),
            )
            .order_by(
                func.extract("year", Expense.created_at),
                func.extract("month", Expense.created_at),
            )
        )
        result = await self.db.execute(stmt)
        return [
            {
                "year": row.year,
                "month": row.month,
                "total_amount": Decimal(str(row.total_amount)),
                "expense_count": int(row.expense_count),
            }
            for row in result.all()
        ]

    async def get_user_active_groups_count(self, user_id: uuid.UUID) -> int:
        result = await self.db.scalar(
            select(func.count(GroupMember.id)).where(
                GroupMember.user_id == user_id,
                GroupMember.status == MemberStatus.ACTIVE,
            )
        )
        return int(result or 0)
