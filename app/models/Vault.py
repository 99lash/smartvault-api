from sqlmodel import Field, Relationship
import enum
from typing import Optional, List
from .Model import Model  # base model with id
from .Log import Log

# ENUM VaultStatus
class VaultStatus(str, enum.Enum):
    locked = "locked"
    unlocked = "unlocked"
    tampered = "tampered"

# CLASS Vault
class Vault(Model, table=True):
    __tablename__ = "vaults"  # optional, explicitly names the table

    name: str = Field(nullable=False, unique=True)           # vault name
    location: Optional[str] = Field(default=None, nullable=True)  # optional location
    status: VaultStatus = Field(default=VaultStatus.locked, nullable=False)  # default status

    logs: List["Log"] = Relationship(back_populates="vault")
