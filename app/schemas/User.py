from sqlmodel import SQLModel
from pydantic import EmailStr
from app.models.User import UserRole
from datetime import datetime

# ----------------------------
# User HTTP Request Schemas
# ----------------------------

class UserCreate(SQLModel, table=False):
  username: str
  email: EmailStr
  password: str

class UserLogin(SQLModel, table=False):
  username: str
  password: str

class UpdateUserRole(SQLModel, table=False):
  role: UserRole


# ----------------------------
# User HTTP Response Schemas
# ----------------------------
# Tiyaka na 'to kasi yung response naman ay nagawa na sa `app/models/User.py`
class UserRead(SQLModel, table=False):
  id: int
  username: str
  email: EmailStr
  password_hash: str
  # ** Pwedeng i-modify rito yung user properties ng HTTP response.
  # ** Example: i-comment mo or tanggalin mo yung `password_hash` property.    
  role: UserRole
  created_at: datetime
  updated_at: datetime | None
  deleted_at: datetime | None
  
  class Config: 
    from_attributes = True