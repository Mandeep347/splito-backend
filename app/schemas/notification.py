import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str | None
    message: str | None
    is_read: bool
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, obj) -> "NotificationResponse":
        """
        Maps metadata_ (SQLAlchemy column alias) → metadata (API field).
        Called explicitly in service layer to avoid field name mismatch.
        """
        return cls(
            id=obj.id,
            type=obj.type,
            title=obj.title,
            message=obj.message,
            is_read=obj.is_read,
            metadata=obj.metadata_,
            created_at=obj.created_at,
        )


class ReadAllResponse(BaseModel):
    updated_count: int
