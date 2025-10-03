from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import enum

if TYPE_CHECKING:
    from .User import User
    from .Vault import Vault

# Enum for membership roles
class MembershipRole(str, enum.Enum):
    admin = "admin"
    member = "member"
    guest = "guest"

class VaultMembership(SQLModel, table=True):
    """
    Represents the relationship between users and vaults with role-based access control.

    This table manages which users have access to which vaults and what permissions
    they have within those vaults.
    """
    __tablename__ = "vault_memberships"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign keys
    user_id: int = Field(foreign_key="users.id", nullable=False)
    vault_id: str = Field(foreign_key="vaults.id", nullable=False)

    # Membership details
    role: MembershipRole = Field(default=MembershipRole.member, nullable=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: Optional[datetime] = Field(default=None, nullable=True)

    # Unique constraint to prevent duplicate memberships
    __table_args__ = (
        UniqueConstraint("user_id", "vault_id", name="uq_vault_membership_user_vault"),
    )

    # Relationships
    user: Optional["User"] = Relationship(back_populates="vault_memberships")
    vault: Optional["Vault"] = Relationship(back_populates="vault_memberships")

    def __repr__(self):
        return f"<VaultMembership(id={self.id}, user_id={self.user_id}, vault_id={self.vault_id}, role={self.role})>"