"""
Analytics service.
Orchestrates repository calls and assembles response schemas.
No SQL here — that lives entirely in analytics_repository.py.
"""
import uuid
from calendar import month_abbr
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import GroupNotFoundError, UserNotInGroupError
from app.domain.group.models import Group, GroupStatus
from app.domain.user.models import User
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.group_repository import GroupMemberRepository
from app.schemas.analytics import (
    GroupAnalyticsResponse,
    GroupSpendingSummary,
    MemberSpendingSummary,
    MonthlySpending,
    UserAnalyticsResponse,
)


def _month_label(year: int, month: int) -> str:
    """e.g. (2026, 1) → 'Jan 2026'"""
    return f"{month_abbr[month]} {year}"


def _build_monthly(rows: list[dict]) -> list[MonthlySpending]:
    return [
        MonthlySpending(
            year=r["year"],
            month=r["month"],
            month_label=_month_label(r["year"], r["month"]),
            total_amount=r["total_amount"],
            expense_count=r["expense_count"],
        )
        for r in rows
    ]


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = AnalyticsRepository(db)
        self.member_repo = GroupMemberRepository(db)

    # ── Group Analytics ───────────────────────────────────────────────────────

    async def get_group_analytics(
        self, group_id: uuid.UUID, requester_id: uuid.UUID
    ) -> GroupAnalyticsResponse:
        # Guard: requester must be active member
        membership = await self.member_repo.get_active_membership(group_id, requester_id)
        if not membership:
            raise UserNotInGroupError("You are not a member of this group.")

        group = await self.db.scalar(select(Group).where(Group.id == group_id))
        if not group or group.status == GroupStatus.ARCHIVED:
            raise GroupNotFoundError(f"Group {group_id} not found.")

        # ── Fetch all metrics in parallel-ish (sequential async is fine here) ──
        total_amount, expense_count = await self.repo.get_group_total_expenses(group_id)
        total_settlements = await self.repo.get_group_total_settlements(group_id)
        largest_amount, largest_title = await self.repo.get_group_largest_expense(group_id)
        avg_amount = await self.repo.get_group_average_expense(group_id)
        member_rows = await self.repo.get_member_spending_breakdown(group_id)
        monthly_rows = await self.repo.get_group_monthly_spending(group_id, months=12)

        # Settlement rate — % of total expenses that have been settled
        if total_amount > Decimal("0"):
            settlement_rate = (
                min(total_settlements / total_amount * 100, Decimal("100"))
            ).quantize(Decimal("0.01"))
        else:
            settlement_rate = Decimal("0")

        # Build member summaries
        members: list[MemberSpendingSummary] = []
        top_spender_name: str | None = None
        top_paid = Decimal("-1")

        for row in member_rows:
            pct = (
                (row["total_paid"] / total_amount * 100).quantize(Decimal("0.01"))
                if total_amount > 0
                else Decimal("0")
            )
            members.append(
                MemberSpendingSummary(
                    user_id=row["user_id"],
                    name=row["name"],
                    total_paid=row["total_paid"],
                    total_owed=row["total_owed"],
                    net_balance=row["net_balance"],
                    expense_count=row["expense_count"],
                    percentage_of_total=pct,
                )
            )
            if row["total_paid"] > top_paid:
                top_paid = row["total_paid"]
                top_spender_name = row["name"]

        return GroupAnalyticsResponse(
            group_id=group_id,
            group_name=group.name,
            currency=group.default_currency,
            total_expenses_amount=total_amount,
            total_expense_count=expense_count,
            total_settlements_amount=total_settlements,
            settlement_rate=settlement_rate,
            average_expense_amount=avg_amount,
            largest_expense_amount=largest_amount,
            largest_expense_title=largest_title,
            members=members,
            top_spender_name=top_spender_name if top_paid > 0 else None,
            monthly_spending=_build_monthly(monthly_rows),
        )

    # ── User Analytics ────────────────────────────────────────────────────────

    async def get_user_analytics(self, user_id: uuid.UUID) -> UserAnalyticsResponse:
        user = await self.db.scalar(select(User).where(User.id == user_id))

        total_paid, expense_count = await self.repo.get_user_total_paid_all_groups(user_id)
        owed_to_others, others_owe_user = await self.repo.get_user_balance_totals(user_id)
        net_balance = others_owe_user - owed_to_others
        groups_count = await self.repo.get_user_active_groups_count(user_id)
        group_rows = await self.repo.get_user_group_breakdown(user_id)
        monthly_rows = await self.repo.get_user_monthly_spending(user_id, months=12)

        # Per-group summaries
        group_summaries: list[GroupSpendingSummary] = [
            GroupSpendingSummary(
                group_id=row["group_id"],
                group_name=row["group_name"],
                total_spent=row["total_spent"],
                user_paid=row["user_paid"],
                user_owed=row["user_owed"],
                expense_count=row["expense_count"],
                currency=row["currency"],
            )
            for row in group_rows
        ]

        most_expensive_group = group_summaries[0].group_name if group_summaries else None

        return UserAnalyticsResponse(
            user_id=user_id,
            user_name=user.name if user else "Unknown",
            total_paid_all_groups=total_paid,
            total_owed_to_others=owed_to_others,
            total_others_owe_user=others_owe_user,
            net_balance=net_balance,
            total_groups_count=groups_count,
            total_expense_count=expense_count,
            groups=group_summaries,
            most_expensive_group_name=most_expensive_group,
            monthly_spending=_build_monthly(monthly_rows),
        )
