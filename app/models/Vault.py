from sqlmodel import Field, Relationship
from typing import Optional, List, TYPE_CHECKING
import enum
from .Model import Model  # base model with id

if TYPE_CHECKING:
    from .Log import Log
    from .VaultMembership import VaultMembership
    from .VaultInvitation import VaultInvitation

# ENUM VaultStatus
class VaultStatus(str, enum.Enum):
    locked = "locked"
    unlocked = "unlocked"
    tampered = "tampered"

class Vault(Model, table=True):
    """
    Represents a physical smart vault device.

    Each vault is uniquely identified by its device_id, which corresponds
    to the ESP32 device's unique identifier. This ensures direct mapping
    between physical devices and database records.
    """
    __tablename__ = "vaults"

    # Device ID serves as the primary identifier (same as id field)
    device_id: str = Field(nullable=False, unique=True, description="ESP32 device identifier")
    name: str = Field(nullable=False, unique=True, description="Human-readable vault name")
    location: Optional[str] = Field(default=None, nullable=True, description="Physical location")
    status: VaultStatus = Field(default=VaultStatus.locked, nullable=False, description="Current vault status")

    # Relationships
    logs: Optional[List["Log"]] = Relationship(back_populates="vault")
    vault_memberships: Optional[List["VaultMembership"]] = Relationship(back_populates="vault")
    vault_invitations: Optional[List["VaultInvitation"]] = Relationship(back_populates="vault")

    def __init__(self, **kwargs):
        """
        Initialize vault with device_id as primary identifier.

        Args:
            **kwargs: Model fields including device_id, name, location, status
        """
        # Ensure device_id is provided
        if not kwargs.get('device_id'):
            raise ValueError("device_id is required for vault creation")

        # Don't remove datetime fields - let the base Model handle them properly
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Vault(id={self.id}, device_id={self.device_id}, name={self.name}, status={self.status})>"
