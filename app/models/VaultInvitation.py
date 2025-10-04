"""
VAULT INVITATION MODEL - Complete Documentation
==============================================

This file defines the data model for vault invitations in the Smart Vault system.
It manages the process of inviting users to join vaults with specific roles.

CONTEXT:
---------
When users need to share vault access with others, they need a secure way to:
1. Generate time-limited invitations
2. Control what role the invited user will have
3. Track invitation status and usage
4. Prevent unauthorized access

This model implements a secure invitation system that acts as a "pending membership"
until the user accepts the invitation and becomes a full vault member.

BUSINESS WORKFLOW:
------------------
1. Vault admin creates invitation with specific role and expiration
2. System generates unique invite code (UUID)
3. Invitation sent to user (via email, app notification, etc.)
4. User accepts invitation using the code
5. System converts invitation to vault membership
6. Invitation marked as accepted and can no longer be used 

BUSINESS RULES:
---------------
1. Each invitation is unique and can only be used once
2. Invitations expire after 1 days by default
3. Only unused, non-expired invitations can be accepted
4. Invitation role determines the membership role upon acceptance
5. System tracks who created each invitation for audit purposes
"""

from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta
import enum
import uuid

# Type-only imports to avoid circular dependency issues
# These are only used for type hints, not at runtime
if TYPE_CHECKING:
    from .User import User      # User model for relationship typing
    from .Vault import Vault    # Vault model for relationship typing


# =============================================================================
# INVITATION ROLE ENUMERATION
# =============================================================================

class InvitationRole(str, enum.Enum):
    """
    Defines the roles that can be assigned through invitations.

    IMPORTANT:
    -----------
    These roles MUST match the MembershipRole enum in VaultMembership model.
    When an invitation is accepted, the invitation role becomes the membership role.

    CONSISTENCY REQUIREMENT:
    ------------------------
    InvitationRole.admin == MembershipRole.admin
    InvitationRole.member == MembershipRole.member
    InvitationRole.guest == MembershipRole.guest

    This ensures seamless conversion from invitation to membership.
    """
    admin = "admin"    # Will grant admin privileges in the vault
    member = "member"  # Will grant standard member privileges
    guest = "guest"    # Will grant limited/guest privileges


# =============================================================================
# VAULT INVITATION MODEL
# =============================================================================

class VaultInvitation(SQLModel, table=True):
    """
    SECURE INVITATION SYSTEM: Manages pending vault memberships.

    PURPOSE:
    --------
    This table implements a secure, auditable invitation system that serves as
    a "staging area" for new vault memberships. It provides:

    1. SECURE ACCESS: Unique codes that can't be guessed or reused
    2. TIME LIMITS: Automatic expiration to reduce security risks
    3. AUDIT TRAIL: Complete tracking of invitation lifecycle
    4. ROLE CONTROL: Pre-defined roles prevent privilege escalation

    INVITATION LIFECYCLE:
    --------------------
    1. CREATED: Admin generates invitation with role and expiration
    2. PENDING: Invitation is valid but not yet accepted
    3. ACCEPTED: User accepts invitation, becomes vault member
    4. EXPIRED: Invitation past expiration date, can no longer be used

    RELATIONSHIP TO MEMBERSHIP:
    ---------------------------
    This is a "pending membership" - when accepted, it creates a VaultMembership
    record with the same vault_id, user_id, and role, then marks itself as accepted.
    """

    __tablename__ = "vault_invitations"

    # -------------------------------------------------------------------------
    # PRIMARY KEY
    # -------------------------------------------------------------------------
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    # -------------------------------------------------------------------------
    # FOREIGN KEY REFERENCES
    # -------------------------------------------------------------------------
    vault_id: int = Field(
        foreign_key="vaults.id",
        nullable=False,
    )

    invited_by: int = Field(
        foreign_key="users.id",
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # INVITATION SECURITY DETAILS
    # -------------------------------------------------------------------------
    invite_code: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        unique=True,
        index=True,
        nullable=False,
    )

    role: InvitationRole = Field(
        default=InvitationRole.member,
        nullable=False,
    )

    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=1),
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # INVITATION STATUS
    # -------------------------------------------------------------------------
    accepted: bool = Field(
        default=False,
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # AUDIT TIMESTAMPS
    # -------------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # DATABASE CONSTRAINTS
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Ensure invite codes are unique across the entire system
        # This is critical for security - prevents code collisions
        UniqueConstraint(
            "invite_code",
            name="uq_vault_invitation_code"
        ),
    )

    # -------------------------------------------------------------------------
    # RELATIONSHIP DEFINITIONS
    # -------------------------------------------------------------------------
    vault: Optional["Vault"] = Relationship(
        back_populates="vault_invitations",
    )

    inviter: Optional["User"] = Relationship(
        back_populates="sent_invitations",
    )

    # -------------------------------------------------------------------------
    # BUSINESS LOGIC METHODS
    # -------------------------------------------------------------------------

    def is_expired(self) -> bool:
        """
        Check if the invitation has passed its expiration time.

        RETURNS:
        --------
        bool: True if current time is past expires_at, False otherwise

        BUSINESS IMPACT:
        ---------------
        Expired invitations cannot be accepted, providing security through time limits.
        """
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """
        Check if the invitation can still be accepted.

        VALIDATION CRITERIA:
        -------------------
        1. Not yet accepted (accepted=False)
        2. Not expired (current time < expires_at)

        RETURNS:
        --------
        bool: True if invitation can be accepted, False otherwise

        USE CASES:
        ---------
        - UI should only show valid invitations to users
        - API should reject acceptance attempts for invalid invitations
        - Cleanup processes can identify and remove invalid invitations
        """
        return not self.accepted and not self.is_expired()

    # -------------------------------------------------------------------------
    # OBJECT REPRESENTATION
    # -------------------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Human-readable string representation of the invitation.

        USEFUL FOR:
        -----------
        - Debugging and logging invitation issues
        - Development console output
        - Error messages and traces
        - Admin dashboards showing invitation status

        FORMAT:
        -------
        <VaultInvitation(id=1, vault_id=3, role=member, accepted=False)>
        """
        return (
            f"<VaultInvitation(id={self.id}, vault_id={self.vault_id}, "
            f"role={self.role}, accepted={self.accepted})>"
        )


# =============================================================================
# COMMON QUERY PATTERNS (for reference)
# =============================================================================
"""
WHEN WORKING WITH THIS MODEL, YOU'LL COMMONLY NEED:

1. FIND PENDING INVITATIONS FOR A VAULT:
   db.query(VaultInvitation).filter(
       VaultInvitation.vault_id == vault_id,
       VaultInvitation.accepted == False,
       VaultInvitation.expires_at > datetime.utcnow()
   ).all()

2. FIND INVITATIONS CREATED BY A USER:
   db.query(VaultInvitation).filter(
       VaultInvitation.invited_by == user_id
   ).all()

3. FIND INVITATION BY CODE:
   db.query(VaultInvitation).filter(
       VaultInvitation.invite_code == code
   ).first()

4. GET EXPIRED INVITATIONS FOR CLEANUP:
   db.query(VaultInvitation).filter(
       VaultInvitation.expires_at <= datetime.utcnow(),
       VaultInvitation.accepted == False
   ).all()

5. CHECK IF USER WAS INVITED TO VAULT:
   invitation = db.query(VaultInvitation).filter(
       VaultInvitation.vault_id == vault_id,
       VaultInvitation.invited_by == inviter_id,
       VaultInvitation.accepted == False
   ).first()

6. CONVERT INVITATION TO MEMBERSHIP:
   if invitation and invitation.is_valid():
       # Create membership
       membership = VaultMembership(
           user_id=user_id,
           vault_id=invitation.vault_id,
           role=invitation.role
       )
       db.add(membership)

       # Mark invitation as used
       invitation.accepted = True
       db.commit()

7. BULK INVITATION OPERATIONS:
   # Get all valid invitations for a user across all vaults
   valid_invitations = db.query(VaultInvitation).filter(
       VaultInvitation.invited_by == user_id,
       VaultInvitation.accepted == False
   ).all()

   # Get invitation statistics for a vault
   total_invitations = db.query(VaultInvitation).filter(
       VaultInvitation.vault_id == vault_id
   ).count()

   pending_invitations = db.query(VaultInvitation).filter(
       VaultInvitation.vault_id == vault_id,
       VaultInvitation.accepted == False,
       VaultInvitation.expires_at > datetime.utcnow()
   ).count()
"""