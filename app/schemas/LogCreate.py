from pydantic import BaseModel, Field
from typing import Optional
from app.models.Log import LogEventType

class LogCreate(BaseModel):
    vault_id: int = Field(..., ge=1, description="The ID of the vault associated with the log")
    event_type: LogEventType = Field(..., description="The type of log event")
    user_id: Optional[int] = Field(None, ge=1, description="The ID of the user who triggered the event (optional)")
    details: Optional[str] = Field(None, max_length=1000, description="Additional details about the event")