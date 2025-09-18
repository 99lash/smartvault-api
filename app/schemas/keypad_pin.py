from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime

# ----------------------------
# Keypad Pin HTTP Request Schemas
# ----------------------------
class KeypadPinCreate(SQLModel, table=False):
  user_id: Optional[int] = None
  pin_code: str

class KeypadPinAssign(SQLModel, table=False):
  user_id: int

# ----------------------------
# Keypad Pin HTTP Response Schemas
# ----------------------------
class KeypadPinRead(SQLModel, table=False):
  id: int
  user_id: Optional[int] = None
  pin_code: str
  created_at: datetime
  updated_at: Optional[datetime] = None
  deleted_at: Optional[datetime] = None
