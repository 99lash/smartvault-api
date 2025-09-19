from pydantic import EmailStr, BaseModel
from app.models.User import UserRole
from datetime import datetime
from typing import Optional

# ----------------------------
# User HTTP Request Schemas
# ----------------------------
class UserCreate(BaseModel):
  username: str
  email: EmailStr
  password: str

class UserLogin(BaseModel):
  username: str
  password: str

class UpdateUserRole(BaseModel):
  role: UserRole

class UserRegister(BaseModel):
  username: str
  email: EmailStr
  password: str
  confirmPassword: str

# ----------------------------
# User HTTP Response Schemas
# ----------------------------
class UserRead(BaseModel):
  id: int
  username: str
  email: EmailStr
  # password_hash: str
  # ** Pwedeng i-modify rito yung user properties ng HTTP response.
  # ** Example: i-uncomment mo password_hash property or tanggalin mo yung ibang properties.    
  role: UserRole
  created_at: datetime
  updated_at: Optional[datetime] = None
  deleted_at: Optional[datetime] = None
  
  class Config: 
    from_attributes = True