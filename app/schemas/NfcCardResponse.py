from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
class NfcCardResponse(BaseModel):
    """
    Schema for returning NFC card information in API responses.
    """
    id: int
    uid: str
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True