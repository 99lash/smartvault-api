"""
VAULT MEMBERSHIP MODEL - Complete Documentation
=============================================

This file defines the data model for vault membership relationships in the Smart Vault system.
It manages which users have access to which vaults and what permissions they have.

CONTEXT:
---------
In a smart vault system, multiple users need to share access to physical vaults (lockboxes).
This model creates the many-to-many relationship between users and vaults, with role-based
permissions to control what each user can do within each vault.

BUSINESS RULES:
---------------
1. A user can be a member of multiple vaults
2. A vault can have multiple users as members
3. Each user-vault relationship must have exactly one role
4. No duplicate user-vault memberships are allowed
5. When a membership is updated, the timestamp should be refreshed
6. All memberships are automatically timestamped on creation

ROLE-BASED ACCESS CONTROL:
--------------------------
- ADMIN: Full control over vault, can manage other users' access
- MEMBER: Standard access to vault contents and operations
- GUEST: Limited/read-only access to vault

DATABASE DESIGN:
-----------------
The model uses a junction table pattern with these key characteristics:
- Composite unique constraint prevents duplicate memberships
- Foreign key indexes for performance on common queries
- Automatic timestamp management via SQLAlchemy events
- Proper relationship loading for efficient queries
"""

from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import event
import enum

# Type-only imports to avoid circular dependency issues
# These are only used for type hints, not at runtime
if TYPE_CHECKING:
    from .User import User      # User model for relationship typing
    from .Vault import Vault    # Vault model for relationship typing


# =============================================================================
# MEMBERSHIP ROLE ENUMERATION
# =============================================================================

class MembershipRole(str, enum.Enum):
    """
    Defines the possible roles a user can have within a vault.

    WHY THESE ROLES?
    -----------------
    Different users need different levels of access to vaults:
    - Admins manage the vault and other users' access
    - Members use the vault for daily operations
    - Guests have limited/view-only access

    ROLE HIERARCHY:
    ---------------
    admin > member > guest (in terms of permissions)

    STRING ENUM:
    ------------
    Uses str as base to ensure JSON serialization works properly
    and API responses are human-readable.
    """
    admin = "admin"    # Full vault management and user administration rights
    member = "member"  # Standard vault access for daily operations
    guest = "guest"    # Limited/read-only access to vault contents


# =============================================================================
# VAULT MEMBERSHIP MODEL
# =============================================================================

class VaultMembership(SQLModel, table=True):
    """
    JUNCTION TABLE: Many-to-Many relationship between Users and Vaults with roles.

    PURPOSE:
    --------
    This table solves the complex access control problem in a multi-user vault system:
    - Multiple users share access to physical vaults (lockboxes)
    - Each user needs different permissions within each vault
    - Access needs to be easily manageable and auditable

    RELATIONSHIPS:
    --------------
    - One user can access many vaults (one-to-many from User perspective)
    - One vault can be accessed by many users (one-to-many from Vault perspective)
    - Each user-vault pair has exactly one role defining their permissions

    DATA INTEGRITY:
    ---------------
    - Unique constraint prevents duplicate user-vault memberships
    - Foreign key constraints ensure referential integrity
    - Database-level constraints prevent orphaned records
    """

    __tablename__ = "vault_memberships"

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
    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,  # Database index for faster user-based queries
    )

    vault_id: int = Field(
        foreign_key="vaults.id",
        nullable=False,
        index=True,  # Database index for faster vault-based queries
    )

    # -------------------------------------------------------------------------
    # MEMBERSHIP DETAILS
    # -------------------------------------------------------------------------
    role: MembershipRole = Field(
        default=MembershipRole.member,
        nullable=False,
    )

    # -------------------------------------------------------------------------
    # AUDIT TIMESTAMPS
    # -------------------------------------------------------------------------
    created_at: datetime = Field(
        default_factory=datetime.now,  # Use local time instead of UTC
        nullable=False,
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        nullable=True,
    )

    # -------------------------------------------------------------------------
    # DATABASE CONSTRAINTS
    # -------------------------------------------------------------------------
    __table_args__ = (
        # Prevent duplicate user-vault memberships at database level
        # This is critical for data integrity - ensures one user can't have
        # multiple roles in the same vault simultaneously
        UniqueConstraint(
            "user_id",
            "vault_id",
            name="uq_vault_membership_user_vault"
        ),
    )

    # -------------------------------------------------------------------------
    # RELATIONSHIP DEFINITIONS
    # -------------------------------------------------------------------------
    user: Optional["User"] = Relationship(
        back_populates="vault_memberships",
    )

    vault: Optional["Vault"] = Relationship(
        back_populates="vault_memberships",
    )

    # -------------------------------------------------------------------------
    # OBJECT REPRESENTATION
    # -------------------------------------------------------------------------
    def __repr__(self) -> str:
        """
        Human-readable string representation of the membership.

        USEFUL FOR:
        -----------
        - Debugging and logging
        - Development console output
        - Error messages and traces

        FORMAT:
        -------
        <VaultMembership(id=1, user_id=5, vault_id=3, role=admin)>
        """
        return (
            f"<VaultMembership(id={self.id}, user_id={self.user_id}, "
            f"vault_id={self.vault_id}, role={self.role})>"
        )


# =============================================================================
# AUTOMATIC TIMESTAMP MANAGEMENT
# =============================================================================

@event.listens_for(VaultMembership, "before_update", propagate=True)
def set_updated_at(mapper, connection, target):
    """
    AUTOMATICALLY UPDATE TIMESTAMP ON ANY CHANGES.

    WHY AUTOMATIC?
    --------------
    Ensures audit trail is always maintained without relying on
    application code to remember to update timestamps.

    PROPAGATION:
    ------------
    propagate=True ensures this works even when updating through
    relationships (e.g., user.vault_memberships.append(...))

    BUSINESS VALUE:
    ---------------
    Provides accurate audit trail for compliance and debugging.
    """
    target.updated_at = datetime.now()  # Use local time instead of UTC


@event.listens_for(VaultMembership, "before_insert", propagate=True)
def set_created_updated_at(mapper, connection, target):
    """
    AUTOMATICALLY SET BOTH TIMESTAMPS ON CREATION.

    WHY BOTH TIMESTAMPS?
    --------------------
    - created_at: Immutable record of when membership was established
    - updated_at: Tracks when permissions were last changed

    DEFENSIVE PROGRAMMING:
    ----------------------
    Checks if created_at is already set (in case of data imports or
    special creation scenarios) before overwriting it.

    CONSISTENCY:
    ------------
    Ensures both timestamps are identical at creation time.
    """
    now = datetime.now()  # Use local time instead of UTC
    if not target.created_at:
        target.created_at = now
    target.updated_at = now


# =============================================================================
# COMMON QUERY PATTERNS (for reference)
# =============================================================================
"""
WHEN WORKING WITH THIS MODEL, YOU'LL COMMONLY NEED:

1. FIND ALL USERS IN A VAULT:
   db.query(VaultMembership).filter(VaultMembership.vault_id == vault_id).all()

2. FIND ALL VAULTS A USER CAN ACCESS:
   db.query(VaultMembership).filter(VaultMembership.user_id == user_id).all()

3. CHECK IF USER IS ADMIN OF VAULT:
   membership = db.query(VaultMembership).filter(
       VaultMembership.user_id == user_id,
       VaultMembership.vault_id == vault_id
   ).first()
   return membership and membership.role == MembershipRole.admin

4. GET MEMBERS WITH USER DETAILS:
   db.query(VaultMembership, User.username, User.first_name, User.last_name)\
       .join(User)\
       .filter(VaultMembership.vault_id == vault_id)\
       .all()

5. CHANGE USER'S ROLE IN VAULT:
   membership = db.query(VaultMembership).filter(
       VaultMembership.user_id == user_id,
       VaultMembership.vault_id == vault_id
   ).first()
   if membership:
       membership.role = new_role
       db.commit()
"""
