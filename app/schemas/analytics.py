"""
Analytics response schemas.
All monetary amounts are Decimal strings (e.g. "3000.00").
All percentages are rounded to 2 decimal places.
"""
import uuid
from decimal import Decimal

from pydantic import BaseModel


# ─── Shared building blocks ───────────────────────────────────────────────────

class MonthlySpending(BaseModel):
    """Spending total for a single calendar month."""
    year: int
    month: int                  # 1–12
    month_label: str            # e.g. "Jan 2026"
    total_amount: Decimal
    expense_count: int


class MemberSpendingSummary(BaseModel):
    """Per-member breakdown within a group."""
    user_id: uuid.UUID
    name: str
    total_paid: Decimal         # sum of expenses where paid_by = this user
    total_owed: Decimal         # sum of owed_amount across all expenses
    net_balance: Decimal        # positive = is owed money, negative = owes money
    expense_count: int          # number of expenses this user paid for
    percentage_of_total: Decimal  # share of group's total spend


class GroupSpendingSummary(BaseModel):
    """Per-group breakdown for user-level analytics."""
    group_id: uuid.UUID
    group_name: str
    total_spent: Decimal        # total expense amount in this group
    user_paid: Decimal          # amount this user paid in this group
    user_owed: Decimal          # amount this user owes in this group
    expense_count: int
    currency: str


# ─── Group Analytics Response ─────────────────────────────────────────────────

class GroupAnalyticsResponse(BaseModel):
    group_id: uuid.UUID
    group_name: str
    currency: str

    # ── Totals ────────────────────────────────────────────────────────────────
    total_expenses_amount: Decimal      # sum of all active expense amounts
    total_expense_count: int            # number of active expenses
    total_settlements_amount: Decimal   # sum of all settlements recorded
    settlement_rate: Decimal            # settlements / total_expenses * 100 (%)
    average_expense_amount: Decimal     # mean expense amount
    largest_expense_amount: Decimal
    largest_expense_title: str | None

    # ── Member breakdown ──────────────────────────────────────────────────────
    members: list[MemberSpendingSummary]
    top_spender_name: str | None        # member who paid the most

    # ── Time series (last 12 months) ──────────────────────────────────────────
    monthly_spending: list[MonthlySpending]   # ordered oldest → newest


# ─── User Analytics Response ──────────────────────────────────────────────────

class UserAnalyticsResponse(BaseModel):
    user_id: uuid.UUID
    user_name: str

    # ── Cross-group totals ────────────────────────────────────────────────────
    total_paid_all_groups: Decimal      # total amount this user paid across all groups
    total_owed_to_others: Decimal       # total this user currently owes others (sum of positive balances)
    total_others_owe_user: Decimal      # total others owe this user (sum of negative balances)
    net_balance: Decimal                # positive = overall creditor, negative = overall debtor
    total_groups_count: int             # number of active groups user belongs to
    total_expense_count: int            # total expenses paid by this user across all groups

    # ── Per-group breakdown ───────────────────────────────────────────────────
    groups: list[GroupSpendingSummary]
    most_expensive_group_name: str | None

    # ── Time series (last 12 months, across all groups) ───────────────────────
    monthly_spending: list[MonthlySpending]   # ordered oldest → newest
