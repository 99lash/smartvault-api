from pydantic import BaseModel, Field, field_validator
from typing import Optional
from app.models.Log import LogEventType

class LogCreate(BaseModel):
    vault_id: int = Field(..., ge=1, description="The ID of the vault associated with the log")
    event_type: LogEventType = Field(..., description="The type of log event")
    details: Optional[str] = Field(None, max_length=1000, description="Additional details about the event")

    @field_validator("event_type", mode="before")
    def normalize_event_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v