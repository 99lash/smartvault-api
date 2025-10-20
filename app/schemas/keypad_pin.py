from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime

# ----------------------------
# Keypad Pin HTTP Request Schemas
# ----------------------------
class KeypadPinCreate(SQLModel, table=False):
   user_id: Optional[int] = None
   vault_id: int
   pin_code: str

class KeypadPinAssign(SQLModel, table=False):
  user_id: int

# ----------------------------
# Keypad Pin HTTP Response Schemas
# ----------------------------
class KeypadPinRead(SQLModel, table=False):
    """
    Enhanced keypad pin response schema with user information for better UI display.

    Includes user details when user_id is present to avoid additional API calls
    for displaying usernames in the mobile app interface.
    """
    id: Optional[int] = None
    user_id: Optional[int] = None
    vault_id: Optional[int] = None
    pin_code: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    # User information for UI display (populated when user_id exists)
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
