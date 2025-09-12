from sqlmodel import SQLModel
from pydantic import EmailStr
from app.models.User import UserRole

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
# User HTTP Request Schemas
# ----------------------------
# Tiyaka na 'to kasi yung response naman ay nagawa na sa `app/models/User.py`