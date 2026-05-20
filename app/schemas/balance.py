import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# ─── Balance ──────────────────────────────────────────────────────────────────

class PairwiseBalance(BaseModel):
    from_user_id: uuid.UUID
    from_user_name: str
    to_user_id: uuid.UUID
    to_user_name: str
    amount: Decimal
    currency: str


class GroupBalancesResponse(BaseModel):
    group_id: uuid.UUID
    currency: str
    balances: list[PairwiseBalance]


class SimplifiedBalance(BaseModel):
    """One entry in the debt-simplified graph — minimises total transactions."""
    from_user_id: uuid.UUID
    from_user_name: str
    to_user_id: uuid.UUID
    to_user_name: str
    amount: Decimal
    currency: str


class SimplifiedBalancesResponse(BaseModel):
    group_id: uuid.UUID
    currency: str
    transactions: list[SimplifiedBalance]


class UserOverallBalance(BaseModel):
    """Cross-group balance summary for the current user."""
    counterpart_user_id: uuid.UUID
    counterpart_name: str
    net_amount: Decimal   # positive = I owe them, negative = they owe me
    currency: str


# ─── Settlement ───────────────────────────────────────────────────────────────

class CreateSettlementRequest(BaseModel):
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    note: str | None = None


class SettlementResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    from_user_id: uuid.UUID
    from_user_name: str
    to_user_id: uuid.UUID
    to_user_name: str
    amount: Decimal
    currency: str
    note: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
