from sqlmodel import SQLModel
from datetime import datetime
from typing import Optional
from app.models.Vault import VaultStatus

# ----------------------------
# Vault HTTP Request Schemas
# ----------------------------
class VaultCreate(SQLModel, table=False):
  name: str
  location: Optional[str] = None

class UpdateVaultStatus(SQLModel, table=False):
  status: VaultStatus

# ----------------------------
# Vault HTTP Response Schemas
# ----------------------------
class VaultRead(SQLModel, table=False):
  id: int
  name: str
  location: Optional[str] = None
  status: VaultStatus
  created_at: datetime
  updated_at: Optional[datetime] = None
  deleted_at: Optional[datetime] = None

  class Config:
    from_attributes = True