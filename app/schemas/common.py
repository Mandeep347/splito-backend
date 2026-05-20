import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: int
    error: str
    message: str
    path: str
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
