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
     id: Optional[int] = None  # Add this missing field
     user_id: Optional[int] = None
     vault_id: Optional[int] = None  # Made optional to handle data inconsistencies
     pin_code: str
     created_at: datetime
     updated_at: Optional[datetime] = None
     deleted_at: Optional[datetime] = None
