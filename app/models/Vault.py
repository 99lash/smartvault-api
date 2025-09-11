from sqlmodel import Field, Relationship
from typing import Optional, List, TYPE_CHECKING
import enum
from .Model import Model  # base model with id

if TYPE_CHECKING:
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

    # Relationships
    logs: Optional[List["Log"]] = Relationship(back_populates="vault")
