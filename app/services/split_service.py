"""
Split strategies follow the Strategy pattern.
Each strategy:
  1. validates the input
  2. returns a list of (user_id, owed_amount) tuples
"""
from abc import ABC, abstractmethod
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from app.core.exceptions import (
    InvalidSplitPercentageError,
    InvalidSplitTotalError,
)
from app.schemas.expense import (
    CreateExpenseRequest,
    EqualParticipant,
    ExactParticipant,
    PercentageParticipant,
    ShareParticipant,
)

TWO_PLACES = Decimal("0.01")


class SplitResult:
    def __init__(self, user_id: UUID, owed_amount: Decimal,
                 percentage: Decimal | None = None, shares: int | None = None):
        self.user_id = user_id
        self.owed_amount = owed_amount
        self.percentage = percentage
        self.shares = shares


class SplitStrategy(ABC):
    @abstractmethod
    def compute(self, total: Decimal, request: CreateExpenseRequest) -> list[SplitResult]:
        ...


class EqualSplitStrategy(SplitStrategy):
    def compute(self, total: Decimal, request: CreateExpenseRequest) -> list[SplitResult]:
        participants: list[EqualParticipant] = request.participants_equal  # type: ignore
        n = len(participants)
        if n == 0:
            raise InvalidSplitTotalError("At least one participant is required.")

        per_person = (total / n).quantize(TWO_PLACES, rounding=ROUND_DOWN)
        # Give the remainder to the first participant (payer typically) to avoid rounding drift
        remainder = total - per_person * n

        results = []
        for i, p in enumerate(participants):
            amount = per_person + remainder if i == 0 else per_person
            results.append(SplitResult(user_id=p.user_id, owed_amount=amount))
        return results


class ExactSplitStrategy(SplitStrategy):
    def compute(self, total: Decimal, request: CreateExpenseRequest) -> list[SplitResult]:
        participants: list[ExactParticipant] = request.participants_exact  # type: ignore
        split_sum = sum(p.owed_amount for p in participants)
        if split_sum != total:
            raise InvalidSplitTotalError(
                f"Exact split amounts sum to {split_sum}, but expense total is {total}."
            )
        return [SplitResult(user_id=p.user_id, owed_amount=p.owed_amount) for p in participants]


class PercentageSplitStrategy(SplitStrategy):
    def compute(self, total: Decimal, request: CreateExpenseRequest) -> list[SplitResult]:
        participants: list[PercentageParticipant] = request.participants_percentage  # type: ignore
        pct_sum = sum(p.percentage for p in participants)
        if pct_sum != Decimal("100"):
            raise InvalidSplitPercentageError(
                f"Percentages must sum to 100, got {pct_sum}."
            )

        results = []
        running = Decimal("0")
        for i, p in enumerate(participants):
            if i < len(participants) - 1:
                amount = (total * p.percentage / 100).quantize(TWO_PLACES, rounding=ROUND_DOWN)
                running += amount
            else:
                # Last participant absorbs rounding error
                amount = total - running
            results.append(SplitResult(user_id=p.user_id, owed_amount=amount, percentage=p.percentage))
        return results


class ShareSplitStrategy(SplitStrategy):
    def compute(self, total: Decimal, request: CreateExpenseRequest) -> list[SplitResult]:
        participants: list[ShareParticipant] = request.participants_share  # type: ignore
        total_shares = sum(p.shares for p in participants)
        if total_shares == 0:
            raise InvalidSplitTotalError("Total shares must be greater than zero.")

        results = []
        running = Decimal("0")
        for i, p in enumerate(participants):
            if i < len(participants) - 1:
                amount = (total * p.shares / total_shares).quantize(TWO_PLACES, rounding=ROUND_DOWN)
                running += amount
            else:
                amount = total - running
            results.append(SplitResult(user_id=p.user_id, owed_amount=amount, shares=p.shares))
        return results


# ─── Factory ──────────────────────────────────────────────────────────────────

_STRATEGIES: dict[str, SplitStrategy] = {
    "EQUAL": EqualSplitStrategy(),
    "EXACT": ExactSplitStrategy(),
    "PERCENTAGE": PercentageSplitStrategy(),
    "SHARE": ShareSplitStrategy(),
}


def get_split_strategy(split_type: str) -> SplitStrategy:
    strategy = _STRATEGIES.get(split_type.upper())
    if not strategy:
        raise ValueError(f"Unknown split type: {split_type}")
    return strategy
