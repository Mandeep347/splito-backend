"""
Unit tests for split strategies.
No DB needed — pure business logic.
"""
from decimal import Decimal

import pytest

from app.core.exceptions import InvalidSplitPercentageError, InvalidSplitTotalError
from app.schemas.expense import (
    CreateExpenseRequest,
    EqualParticipant,
    ExactParticipant,
    PercentageParticipant,
    ShareParticipant,
)
from app.services.split_service import (
    EqualSplitStrategy,
    ExactSplitStrategy,
    PercentageSplitStrategy,
    ShareSplitStrategy,
    get_split_strategy,
)
import uuid

U1 = uuid.uuid4()
U2 = uuid.uuid4()
U3 = uuid.uuid4()


def _req(**kwargs) -> CreateExpenseRequest:
    """Build a minimal CreateExpenseRequest with the given overrides."""
    defaults = dict(
        title="Test",
        total_amount=Decimal("3000"),
        currency="INR",
        paid_by_user_id=U1,
        split_type="EQUAL",
        participants_equal=[
            EqualParticipant(user_id=U1),
            EqualParticipant(user_id=U2),
            EqualParticipant(user_id=U3),
        ],
    )
    defaults.update(kwargs)
    return CreateExpenseRequest(**defaults)


# ── EQUAL ─────────────────────────────────────────────────────────────────────

class TestEqualSplit:
    def test_divides_evenly(self):
        req = _req(total_amount=Decimal("3000"))
        results = EqualSplitStrategy().compute(Decimal("3000"), req)
        assert len(results) == 3
        assert sum(r.owed_amount for r in results) == Decimal("3000")
        assert all(r.owed_amount == Decimal("1000") for r in results)

    def test_rounding_remainder_goes_to_first(self):
        # 100 / 3 = 33.33... → first gets 33.34, others get 33.33
        req = _req(
            total_amount=Decimal("100"),
            participants_equal=[
                EqualParticipant(user_id=U1),
                EqualParticipant(user_id=U2),
                EqualParticipant(user_id=U3),
            ],
        )
        results = EqualSplitStrategy().compute(Decimal("100"), req)
        amounts = sorted([r.owed_amount for r in results], reverse=True)
        assert amounts[0] == Decimal("33.34")
        assert amounts[1] == amounts[2] == Decimal("33.33")
        assert sum(r.owed_amount for r in results) == Decimal("100")

    def test_single_participant(self):
        req = _req(
            total_amount=Decimal("500"),
            participants_equal=[EqualParticipant(user_id=U1)],
        )
        results = EqualSplitStrategy().compute(Decimal("500"), req)
        assert results[0].owed_amount == Decimal("500")

    def test_empty_participants_raises(self):
        # The Pydantic validator catches empty list before strategy is reached
        with pytest.raises(Exception):  # ValidationError from Pydantic
            _req(participants_equal=[])


# ── EXACT ─────────────────────────────────────────────────────────────────────

class TestExactSplit:
    def test_valid_exact_split(self):
        req = _req(
            split_type="EXACT",
            participants_equal=None,
            participants_exact=[
                ExactParticipant(user_id=U1, owed_amount=Decimal("1000")),
                ExactParticipant(user_id=U2, owed_amount=Decimal("500")),
                ExactParticipant(user_id=U3, owed_amount=Decimal("1500")),
            ],
        )
        results = ExactSplitStrategy().compute(Decimal("3000"), req)
        assert sum(r.owed_amount for r in results) == Decimal("3000")

    def test_mismatch_raises(self):
        req = _req(
            split_type="EXACT",
            participants_equal=None,
            participants_exact=[
                ExactParticipant(user_id=U1, owed_amount=Decimal("1000")),
                ExactParticipant(user_id=U2, owed_amount=Decimal("500")),
            ],
        )
        with pytest.raises(InvalidSplitTotalError):
            ExactSplitStrategy().compute(Decimal("3000"), req)


# ── PERCENTAGE ────────────────────────────────────────────────────────────────

class TestPercentageSplit:
    def test_valid_100_percent(self):
        req = _req(
            split_type="PERCENTAGE",
            participants_equal=None,
            participants_percentage=[
                PercentageParticipant(user_id=U1, percentage=Decimal("40")),
                PercentageParticipant(user_id=U2, percentage=Decimal("30")),
                PercentageParticipant(user_id=U3, percentage=Decimal("30")),
            ],
        )
        results = PercentageSplitStrategy().compute(Decimal("3000"), req)
        assert sum(r.owed_amount for r in results) == Decimal("3000")
        amounts = {r.user_id: r.owed_amount for r in results}
        assert amounts[U1] == Decimal("1200")

    def test_not_100_raises(self):
        req = _req(
            split_type="PERCENTAGE",
            participants_equal=None,
            participants_percentage=[
                PercentageParticipant(user_id=U1, percentage=Decimal("50")),
                PercentageParticipant(user_id=U2, percentage=Decimal("40")),
            ],
        )
        with pytest.raises(InvalidSplitPercentageError):
            PercentageSplitStrategy().compute(Decimal("1000"), req)

    def test_rounding_absorbed_by_last(self):
        # 1000 * 33.33% = 333.3 → last absorbs remainder
        req = _req(
            total_amount=Decimal("1000"),
            split_type="PERCENTAGE",
            participants_equal=None,
            participants_percentage=[
                PercentageParticipant(user_id=U1, percentage=Decimal("33.33")),
                PercentageParticipant(user_id=U2, percentage=Decimal("33.33")),
                PercentageParticipant(user_id=U3, percentage=Decimal("33.34")),
            ],
        )
        results = PercentageSplitStrategy().compute(Decimal("1000"), req)
        assert sum(r.owed_amount for r in results) == Decimal("1000")


# ── SHARE ─────────────────────────────────────────────────────────────────────

class TestShareSplit:
    def test_equal_shares(self):
        req = _req(
            split_type="SHARE",
            participants_equal=None,
            participants_share=[
                ShareParticipant(user_id=U1, shares=1),
                ShareParticipant(user_id=U2, shares=1),
                ShareParticipant(user_id=U3, shares=1),
            ],
        )
        results = ShareSplitStrategy().compute(Decimal("3000"), req)
        assert sum(r.owed_amount for r in results) == Decimal("3000")
        assert all(r.owed_amount == Decimal("1000") for r in results)

    def test_weighted_shares(self):
        req = _req(
            total_amount=Decimal("1000"),
            split_type="SHARE",
            participants_equal=None,
            participants_share=[
                ShareParticipant(user_id=U1, shares=2),
                ShareParticipant(user_id=U2, shares=1),
            ],
        )
        results = ShareSplitStrategy().compute(Decimal("1000"), req)
        amounts = {r.user_id: r.owed_amount for r in results}
        # 2/3 and 1/3
        assert amounts[U1] == Decimal("666.66") or amounts[U1] == Decimal("666.67")
        assert sum(r.owed_amount for r in results) == Decimal("1000")


# ── Factory ───────────────────────────────────────────────────────────────────

def test_get_strategy_factory():
    assert isinstance(get_split_strategy("EQUAL"), EqualSplitStrategy)
    assert isinstance(get_split_strategy("EXACT"), ExactSplitStrategy)
    assert isinstance(get_split_strategy("PERCENTAGE"), PercentageSplitStrategy)
    assert isinstance(get_split_strategy("SHARE"), ShareSplitStrategy)

def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        get_split_strategy("MAGIC")
