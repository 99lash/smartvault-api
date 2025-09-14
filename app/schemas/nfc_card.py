from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

# ----------------------------
# NFC Card HTTP Request Schemas
# ----------------------------
class NfcCardCreate(SQLModel, table=False):
    """
    Schema for creating a new NFC card.
    """
    uid: str = Field(..., description="Unique identifier of the NFC card")
    user_id: Optional[int] = Field(None, description="ID of the user to assign the card to (optional)")

class NfcCardAssign(SQLModel, table=False):
    """
    Schema for assigning an NFC card to a user.
    """
    user_id: int

# ----------------------------
# NFC Card HTTP Request Schemas
# ----------------------------

class NfcCardRead(SQLModel, table=False):
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