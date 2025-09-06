from sqlmodel import Field, Relationship
from typing import List
import enum
from .Model import Model # the -> `.` means same folder, the -> `Model` in `.Model` means open Model.py while the Model at the end of the import is the class name
from .Log import Log

# ENUM UserRole
# Enum in Python is still a class, just a special kind of class.
# enum.Enum → makes this a proper Enum type.
# str → means the enum values behave like strings (e.g., "admin", "user"), so they can be stored in a database as text, used in JSON, etc.
class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"

# CLASS User
# It inherits from Model(Model is a Base model that inherets SQLModel, open Model.py for more documentation)
class User(Model, table=True):
    __tablename__ = "users" # Explicitly sets the table’s name in the database as users, Without this, SQLModel would usually just guess from the class name (user).

    username: str = Field(index=True, unique=True, nullable=False) # Defines a column named username.
    email: str = Field(index=True, unique=True, nullable=False)    # Defines a column named eamil.
    password_hash: str                                             # Defines a column named password_hash.
    role: UserRole = Field(default=UserRole.user, nullable=False)  # Defines a column named role.

    logs: List["Log"] = Relationship(back_populates="user")
