from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ----------------------------
# NonAdminUser HTTP Request Schemas
# ----------------------------
class NonAdminUserCreate(BaseModel):
    name: str
    nfc_card_uid: Optional[str] = None  # NFC card UID to assign (will be created if not exists)
    keypad_pin_code: Optional[str] = None  # Keypad PIN code to assign (will be created if not exists)
    user_id: Optional[int] = None  # Existing user account to link to

class NonAdminUserRegister(BaseModel):
    """Schema for registering a non-admin user with NFC card and keypad PIN"""
    name: str
    nfc_card_uid: str  # Required NFC card UID
    keypad_pin_code: str  # Required keypad PIN code
    user_id: Optional[int] = None  # Optional existing user account to link to

# ----------------------------
# NonAdminUser HTTP Response Schemas
# ----------------------------
class NonAdminUserRead(BaseModel):
    id: int
    name: str
    nfc_card_id: Optional[int]
    keypad_pin_id: Optional[int]
    user_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NonAdminUserWithDetails(BaseModel):
    """Response schema that includes related entity details"""
    id: int
    name: str
    nfc_card_id: Optional[int]
    keypad_pin_id: Optional[int]
    user_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True