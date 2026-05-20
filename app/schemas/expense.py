import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


# ─── Participant input variants ───────────────────────────────────────────────

class EqualParticipant(BaseModel):
    user_id: uuid.UUID


class ExactParticipant(BaseModel):
    user_id: uuid.UUID
    owed_amount: Decimal = Field(..., gt=0)


class PercentageParticipant(BaseModel):
    user_id: uuid.UUID
    percentage: Decimal = Field(..., gt=0, le=100)


class ShareParticipant(BaseModel):
    user_id: uuid.UUID
    shares: int = Field(..., gt=0)


# ─── Create Expense ───────────────────────────────────────────────────────────

class CreateExpenseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    total_amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    paid_by_user_id: uuid.UUID
    split_type: str = Field(..., pattern="^(EQUAL|EXACT|PERCENTAGE|SHARE)$")

    # Participant lists — only one should be set depending on split_type
    participants_equal: list[EqualParticipant] | None = None
    participants_exact: list[ExactParticipant] | None = None
    participants_percentage: list[PercentageParticipant] | None = None
    participants_share: list[ShareParticipant] | None = None

    @model_validator(mode="after")
    def check_participants_present(self) -> "CreateExpenseRequest":
        mapping = {
            "EQUAL": self.participants_equal,
            "EXACT": self.participants_exact,
            "PERCENTAGE": self.participants_percentage,
            "SHARE": self.participants_share,
        }
        participants = mapping.get(self.split_type)
        if not participants:
            raise ValueError(
                f"participants_{self.split_type.lower()} must be provided for split_type={self.split_type}"
            )
        return self


class UpdateExpenseRequest(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


# ─── Response ─────────────────────────────────────────────────────────────────

class ParticipantResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    owed_amount: Decimal
    percentage: Decimal | None
    shares: int | None

    model_config = {"from_attributes": True}


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    paid_by_user_id: uuid.UUID
    paid_by_name: str
    title: str
    description: str | None
    total_amount: Decimal
    currency: str
    split_type: str
    status: str
    created_at: datetime
    participants: list[ParticipantResponse] = []

    model_config = {"from_attributes": True}


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedExpenses(BaseModel):
    items: list[ExpenseResponse]
    page: int
    limit: int
    total_pages: int
    total_items: int
