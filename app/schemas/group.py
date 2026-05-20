import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ─── Group ────────────────────────────────────────────────────────────────────

class CreateGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    default_currency: str = Field("INR", min_length=3, max_length=3)


class UpdateGroupRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class GroupMemberResponse(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str
    role: str
    status: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    default_currency: str
    status: str
    created_by: uuid.UUID
    created_at: datetime
    members_count: int = 0

    model_config = {"from_attributes": True}


class GroupDetailResponse(GroupResponse):
    members: list[GroupMemberResponse] = []


# ─── Member management ────────────────────────────────────────────────────────

class AddMemberRequest(BaseModel):
    email: str = Field(..., min_length=1)


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(ADMIN|MEMBER)$")
