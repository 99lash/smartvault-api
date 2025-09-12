from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class NfcCardCreate(BaseModel):
    """
    Schema for creating a new NFC card.
    """
    uid: str = Field(..., description="Unique identifier of the NFC card")
    user_id: Optional[int] = Field(None, description="ID of the user to assign the card to (optional)")
