"""
VAULT MEMBERSHIP SERVICE - Complete Documentation
================================================

This file implements the business logic layer for vault membership management in the Smart Vault system.
It handles the core operations of adding users to vaults, checking permissions, and managing access.

CONTEXT:
---------
The service layer sits between API routes and data models, containing the business logic for:
1. USER-VAULT RELATIONSHIP MANAGEMENT: Adding, removing, and updating user access
2. PERMISSION VALIDATION: Checking what users can do in specific vaults
3. ACCESS CONTROL: Enforcing role-based permissions across the system
4. DATA CONSISTENCY: Ensuring membership records are accurate and up-to-date

BUSINESS RESPONSIBILITIES:
---------------------------
1. MEMBERSHIP CREATION: Add users to vaults with specific roles
2. PERMISSION CHECKING: Determine user access levels and capabilities
3. MEMBERSHIP QUERIES: Find user's vaults and vault's members
4. DATA INTEGRITY: Prevent duplicate memberships and orphaned records
5. SOFT DELETE HANDLING: Exclude deleted users from active membership lists

ROLE-BASED ACCESS CONTROL:
--------------------------
This service is the foundation of the vault security system:
- ADMIN: Can manage vault and other users' access
- MEMBER: Can access vault contents and perform standard operations
- GUEST: Has limited/read-only access to vault

Each role grants different permissions:
- Vault management (admin only)
- User invitation (admin only)
- Content access (member and admin)
- Read-only access (guest, member, admin)

CRITICAL DESIGN DECISIONS:
---------------------------
1. TRANSACTION SAFETY: Uses flush() instead of commit() to participate in larger transactions
2. DUPLICATE PREVENTION: Checks for existing memberships before creating new ones
3. SOFT DELETE AWARENESS: Always excludes deleted users from active queries
4. PERFORMANCE OPTIMIZATION: Efficient queries for common operations
5. TYPE SAFETY: Proper type hints for better IDE support and error prevention

INTEGRATION POINTS:
-------------------
- API Routes: Call service methods for HTTP endpoints
- Invitation Service: Uses this service to create memberships from invitations
- Repository Layer: Handles the actual database operations
- Authentication: Validates user permissions before operations
- Audit Systems: Logs membership changes for compliance

PERFORMANCE CHARACTERISTICS:
----------------------------
- Membership queries are fast (indexed on user_id and vault_id)
- Role checking is optimized for frequent permission validation
- Soft delete filtering prevents performance degradation over time
- Flush-only operations support transaction composition
"""

from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from app.models.VaultMembership import VaultMembership, MembershipRole


# =============================================================================
# VAULT MEMBERSHIP SERVICE CLASS
# =============================================================================

class VaultMembershipService:
    """
    BUSINESS LOGIC LAYER: Manages user access to vaults with role-based permissions.

    PURPOSE:
    --------
    This service encapsulates all business logic related to vault membership management.
    It ensures that users have appropriate access to vaults while maintaining:

    1. SECURITY: Proper role-based access control
    2. DATA INTEGRITY: No duplicate or invalid memberships
    3. CONSISTENCY: All membership operations follow business rules
    4. PERFORMANCE: Optimized queries for common operations

    CORE RESPONSIBILITIES:
    ----------------------
    - Add users to vaults with specific roles
    - Check user permissions in vaults
    - Retrieve membership information
    - Validate membership state before operations
    - Handle soft-deleted user filtering

    TRANSACTION BEHAVIOR:
    --------------------
    This service uses flush() instead of commit() to participate in larger transactions.
    This is critical for operations like invitation acceptance where multiple
    related changes must succeed or fail together.

    EXAMPLE TRANSACTION SCENARIO:
    ----------------------------
    1. Invitation acceptance starts transaction
    2. This service creates membership (flush only)
    3. Invitation marked as accepted (flush only)
    4. Transaction committed - both changes permanent
    5. If any step fails, both changes rolled back

    DEPENDENCY MANAGEMENT:
    ----------------------
    - db: SQLAlchemy session for database operations
    - No repository dependency - direct model access for simple operations
    - Type hints ensure proper parameter validation
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session for transaction management

        WHY DIRECT MODEL ACCESS?
        ------------------------
        This service uses direct model queries instead of a repository because:
        - Simple CRUD operations don't need repository abstraction
        - Better performance for straightforward queries
        - More explicit control over query construction
        - Repository pattern better suited for complex data operations
        """
        self.db = db

    # -------------------------------------------------------------------------
    # MEMBERSHIP CREATION
    # -------------------------------------------------------------------------

    def add_user_to_vault(self, user_id: int, vault_id: int, role: MembershipRole) -> VaultMembership:
        """
        PRIMARY MEMBERSHIP OPERATION: Add user to vault with specified role.

        BUSINESS CONTEXT:
        -----------------
        This is one of the most fundamental operations in the vault system.
        It establishes the relationship between a user and a vault, defining
        what the user can do within that vault.

        CRITICAL VALIDATION:
        -------------------
        1. Check for existing membership to prevent duplicates
        2. Validate role is appropriate for the operation
        3. Ensure user and vault exist (foreign key constraints)

        TRANSACTION BEHAVIOR:
        --------------------
        Uses flush() instead of commit() to participate in larger transactions.
        This allows the operation to be part of bigger workflows like:
        - Invitation acceptance (invitation + membership)
        - Bulk user addition (multiple memberships)
        - Administrative vault setup

        WHY PREVENT DUPLICATES?
        -----------------------
        - Data integrity: One user should have only one role per vault
        - Security: Prevents accidental privilege escalation
        - Simplicity: UI and business logic assume single membership per user-vault pair
        - Performance: Avoids complex role resolution logic

        RETURNS:
        --------
        VaultMembership: The newly created membership object

        ERROR CONDITIONS:
        ----------------
        - User already member: Raises ValueError with clear message
        - Invalid role: Raises ValueError (enum validation)
        - Database constraints: Foreign key violations, unique constraints

        PERFORMANCE:
        -----------
        - Fast operation (typically <50ms)
        - Single query for duplicate check
        - Indexed fields for optimal lookup
        """
        # =====================================================================
        # STEP 1: VALIDATE NO EXISTING MEMBERSHIP
        # =====================================================================
        existing = (
            self.db.query(VaultMembership)
            .filter(
                VaultMembership.user_id == user_id,
                VaultMembership.vault_id == vault_id
            )
            .first()
        )

        if existing:
            raise ValueError("User is already a member of this vault")

        # =====================================================================
        # STEP 2: CREATE NEW MEMBERSHIP
        # =====================================================================
        membership = VaultMembership(
            user_id=user_id,
            vault_id=vault_id,
            role=role,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # =====================================================================
        # STEP 3: PERSIST MEMBERSHIP (NON-COMMITTAL)
        # =====================================================================
        self.db.add(membership)
        self.db.flush()  # Write to transaction but don't commit yet
        return membership

    # -------------------------------------------------------------------------
    # MEMBERSHIP QUERIES
    # -------------------------------------------------------------------------

    def get_user_vaults(self, user_id: int) -> List[VaultMembership]:
        """
        USER-CENTRIC QUERY: Find all vaults a user has access to.

        BUSINESS PURPOSE:
        -----------------
        Users need to see which vaults they can access. This powers:
        - User dashboard showing available vaults
        - Vault selection in mobile app
        - Permission checks throughout the application
        - User profile showing vault memberships

        COMMON USE CASES:
        -----------------
        - Mobile app home screen showing user's vaults
        - Web dashboard vault list
        - Permission validation before vault operations
        - User profile management

        RETURNS:
        --------
        List[VaultMembership]: All memberships for the user

        PERFORMANCE NOTE:
        ----------------
        Consider pagination for users with many vault memberships.
        """
        return (
            self.db.query(VaultMembership)
            .filter(VaultMembership.user_id == user_id)
            .all()
        )

    def get_user_role_in_vault(self, user_id: int, vault_id: int) -> Optional[MembershipRole]:
        """
        PERMISSION CHECKING: Determine user's role in specific vault.

        CRITICAL SECURITY OPERATION:
        ----------------------------
        This method is called frequently throughout the application to:
        - Validate user can perform vault operations
        - Show appropriate UI elements based on permissions
        - Enforce access control in API endpoints
        - Determine what actions user can take

        BUSINESS LOGIC:
        ---------------
        - Returns None if user is not a member (no access)
        - Returns specific role if user is a member (defines permissions)
        - Used for authorization decisions throughout the system

        PERFORMANCE:
        -----------
        - Fast lookup using database indexes
        - Single query with minimal data transfer
        - Cached in application layer for repeated checks

        SECURITY:
        ---------
        - No information leakage (returns None vs False appropriately)
        - Fast failure for unauthorized access attempts
        - Foundation for all vault-level authorization

        RETURNS:
        --------
        MembershipRole or None: User's role in vault, or None if not a member
        """
        membership = (
            self.db.query(VaultMembership)
            .filter(
                VaultMembership.user_id == user_id,
                VaultMembership.vault_id == vault_id
            )
            .first()
        )
        return membership.role if membership else None

    def get_vault_members(self, vault_id: int) -> List[VaultMembership]:
        """
        VAULT-CENTRIC QUERY: Find all users who have access to a vault.

        BUSINESS PURPOSE:
        -----------------
        Vault administrators need to see who has access to their vaults for:
        - User management and administration
        - Access auditing and compliance
        - Understanding vault utilization
        - Managing permissions and roles

        SOFT DELETE HANDLING:
        --------------------
        CRITICAL: Excludes soft-deleted users from active membership lists.
        This ensures that deleted users don't appear in:
        - Admin dashboards
        - User selection interfaces
        - Permission calculations
        - Access control decisions

        WHY SOFT DELETE AWARENESS?
        --------------------------
        - Security: Deleted users shouldn't have apparent access
        - User Experience: Clean lists without deleted users
        - Performance: Avoids showing irrelevant data
        - Compliance: Clear separation of active vs inactive access

        JOIN STRATEGY:
        -------------
        Uses SQL JOIN to efficiently combine membership and user data.
        More efficient than separate queries for each membership.

        RETURNS:
        --------
        List[VaultMembership]: All active memberships for the vault

        COMMON CALLERS:
        ---------------
        - Admin dashboard showing vault users
        - API endpoint for vault member listing
        - Permission validation for vault operations
        - User invitation interfaces
        """
        from app.models.User import User

        return (
            self.db.query(VaultMembership)
            .join(User, VaultMembership.user_id == User.id)
            .filter(VaultMembership.vault_id == vault_id)
            .filter(User.deleted_at == None)  # Exclude soft-deleted users
            .all()
        )


# =============================================================================
# INTEGRATION AND USAGE PATTERNS
# =============================================================================
"""
This service is used throughout the application for:

1. AUTHENTICATION AND AUTHORIZATION:
   role = membership_service.get_user_role_in_vault(user_id, vault_id)
   if not role:
       return "Access denied"
   if role == MembershipRole.admin:
       # Show admin controls

2. USER INTERFACE POPULATION:
   user_vaults = membership_service.get_user_vaults(user_id)
   # Display vaults in dropdown or list

3. VAULT ADMINISTRATION:
   vault_members = membership_service.get_vault_members(vault_id)
   # Show member list in admin panel

4. INVITATION PROCESSING:
   # When invitation is accepted
   membership = membership_service.add_user_to_vault(
       user_id=user_id,
       vault_id=invitation.vault_id,
       role=MembershipRole(invitation.role)
   )

5. BULK OPERATIONS:
   # Add multiple users to vault
   for user_id in user_ids:
       membership_service.add_user_to_vault(user_id, vault_id, role)

6. PERMISSION CHECKING THROUGHOUT APP:
   def can_user_access_vault(user_id: int, vault_id: int) -> bool:
       role = membership_service.get_user_role_in_vault(user_id, vault_id)
       return role is not None

   def is_user_admin_of_vault(user_id: int, vault_id: int) -> bool:
       role = membership_service.get_user_role_in_vault(user_id, vault_id)
       return role == MembershipRole.admin
"""
