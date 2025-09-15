from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime
from app.models.UserVault import UserVault

# ----------------------------
# UserVault HTTP Request Schemas
# ----------------------------
class UserVaultCreate(SQLModel, table=False):
    user_id: int
    vault_id: int

class UserVaultBulkCreate(SQLModel, table=False):
    user_ids: list[int]
    vault_id: int

# ----------------------------
# UserVault HTTP Response Schemas
# ----------------------------
class UserVaultRead(SQLModel, table=False):
    id: Optional[int] = None
    user_id: int
    vault_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True