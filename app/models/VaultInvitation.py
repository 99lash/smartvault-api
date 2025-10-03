from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional, TYPE_CHECKING
from datetime import datetime
import enum
import uuid

if TYPE_CHECKING:
    from .User import User
    from .Vault import Vault

# Enum for invitation roles (should match VaultMembership roles)
class InvitationRole(str, enum.Enum):
    admin = "admin"
    member = "member"
    guest = "guest"

class VaultInvitation(SQLModel, table=True):
    """
    Represents vault invitations sent to users.

    This table manages invitation codes that allow users to join vaults
    with specific roles. Invitations have expiration times and track
    acceptance status.
    """
    __tablename__ = "vault_invitations"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign keys
    vault_id: str = Field(foreign_key="vaults.id", nullable=False)
    invited_by: int = Field(foreign_key="users.id", nullable=False)

    # Invitation details
    invite_code: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        unique=True,
        index=True,
        nullable=False
    )
    role: InvitationRole = Field(default=InvitationRole.member, nullable=False)
    expires_at: datetime = Field(nullable=False)
    accepted: bool = Field(default=False, nullable=False)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Unique constraint on invite_code (already handled by unique=True above)
    __table_args__ = (
        UniqueConstraint("invite_code", name="uq_vault_invitation_code"),
    )

    # Relationships
    vault: Optional["Vault"] = Relationship(back_populates="vault_invitations")
    inviter: Optional["User"] = Relationship(back_populates="sent_invitations")

    def is_expired(self) -> bool:
        """Check if the invitation has expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the invitation is still valid (not expired and not accepted)"""
        return not self.accepted and not self.is_expired()

    def __repr__(self):
        return f"<VaultInvitation(id={self.id}, vault_id={self.vault_id}, role={self.role}, accepted={self.accepted})>"