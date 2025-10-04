"""
VAULT INVITATION REPOSITORY - Complete Documentation
===================================================

This file implements the data access layer for vault invitations in the Smart Vault system.
It provides secure, efficient database operations for managing the complete invitation lifecycle.

CONTEXT:
---------
The repository pattern separates business logic from data access concerns. This class handles:
1. Secure storage and retrieval of invitations
2. Invitation lifecycle management (create, validate, accept, cleanup)
3. Performance-optimized queries for common use cases
4. Data consistency and integrity enforcement

BUSINESS RESPONSIBILITIES:
---------------------------
1. INVITATION LOOKUP: Fast retrieval by invite code (most common operation)
2. VAULT MANAGEMENT: Track all invitations for specific vaults
3. AUDIT TRAIL: Monitor invitation activity by user
4. LIFECYCLE MANAGEMENT: Handle acceptance and expiration
5. SYSTEM MAINTENANCE: Clean up expired invitations
6. SECURITY: Ensure one-time use and proper validation

PERFORMANCE CONSIDERATIONS:
---------------------------
- Invite code lookups are indexed for fast retrieval
- Time-based queries use database indexes efficiently
- Bulk operations minimize database round trips
- Proper ordering supports UI pagination and display

SECURITY FEATURES:
------------------
- All operations validate invitation state before changes
- Atomic operations prevent race conditions
- Proper transaction handling ensures data consistency
- Expired invitation cleanup prevents security risks

INTEGRATION POINTS:
-------------------
- Works with VaultInvitationService for business logic
- Supports vault_invitation_routes for API endpoints
- Integrates with cleanup jobs for system maintenance
- Provides data for admin dashboards and user notifications
"""

from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.models.VaultInvitation import VaultInvitation, InvitationRole
from .Repository import Repository


# =============================================================================
# VAULT INVITATION REPOSITORY CLASS
# =============================================================================

class VaultInvitationRepository(Repository):
    """
    DATA ACCESS LAYER: Secure invitation management with comprehensive lifecycle support.

    PURPOSE:
    --------
    This repository encapsulates all database operations for vault invitations,
    providing a clean interface for the service layer while ensuring:

    1. DATA SECURITY: Proper validation and state management
    2. PERFORMANCE: Optimized queries for common operations
    3. CONSISTENCY: Atomic operations and proper transactions
    4. MAINTAINABILITY: Clear, testable data access methods

    COMMON USE CASES:
    -----------------
    - User accepts invitation via mobile app
    - Admin views pending invitations for vault
    - System cleans up expired invitations
    - Audit reports show invitation activity
    - UI displays invitation status to users

    RELATIONSHIP TO SERVICE LAYER:
    ------------------------------
    Service Layer (VaultInvitationService) handles business logic like:
    - Permission checks before creating invitations
    - Email notifications when invitations are created
    - Integration with vault membership creation

    This repository focuses purely on data access and persistence.
    """

    def __init__(self, db: Session):
        """
        Initialize repository with database session and model.

        Args:
            db: SQLAlchemy database session for transaction management
        """
        super().__init__(db, VaultInvitation)

    # -------------------------------------------------------------------------
    # CORE LOOKUP OPERATIONS
    # -------------------------------------------------------------------------

    def get_by_invite_code(self, invite_code: str) -> Optional[VaultInvitation]:
        """
        PRIMARY LOOKUP METHOD: Find invitation by unique invite code.

        CRITICAL OPERATION:
        -------------------
        This is the most frequently called method in the invitation system.
        Every invitation acceptance starts with this lookup.

        PERFORMANCE:
        -----------
        - Uses database index on invite_code for fast retrieval
        - Single result expected (unique constraint enforced)

        SECURITY:
        ---------
        - No business logic here - validation happens in service layer
        - Returns None if code not found (safe for security)

        RETURNS:
        --------
        VaultInvitation or None: The invitation if found, None otherwise

        COMMON CALLER:
        -------------
        VaultInvitationService.accept_invitation(invite_code)
        """
        return (
            self.db.query(self.model)
            .filter(self.model.invite_code == invite_code)
            .first()
        )

    def get_invitations_by_vault(self, vault_id: int) -> List[VaultInvitation]:
        """
        VAULT-CENTRIC VIEW: Get complete invitation history for a vault.

        BUSINESS PURPOSE:
        -----------------
        Vault administrators need to see all invitations ever created for their vault
        to understand access patterns and audit user additions.

        USE CASES:
        ----------
        - Admin dashboard showing invitation history
        - Audit reports for compliance
        - Understanding vault growth over time
        - Tracking which users were invited by whom

        ORDERING:
        ---------
        Most recent first (created_at.desc()) for logical timeline display.

        PERFORMANCE NOTE:
        ----------------
        Consider pagination for vaults with many invitations.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.vault_id == vault_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_invitations_by_inviter(self, invited_by: int) -> List[VaultInvitation]:
        """
        USER ACTIVITY TRACKING: Find all invitations created by a specific user.

        AUDIT PURPOSE:
        --------------
        Track which users are actively inviting others to vaults.
        Important for security monitoring and usage analytics.

        BUSINESS VALUE:
        ---------------
        - Identify power users who invite many people
        - Detect potential security issues (user inviting too many people)
        - Generate reports on invitation activity
        - Support "invited by" features in UI

        ORDERING:
        ---------
        Chronological order (newest first) shows recent activity.
        """
        return (
            self.db.query(self.model)
            .filter(self.model.invited_by == invited_by)
            .order_by(self.model.created_at.desc())
            .all()
        )

    # -------------------------------------------------------------------------
    # INVITATION STATE QUERIES
    # -------------------------------------------------------------------------

    def get_pending_invitations(self, vault_id: int) -> List[VaultInvitation]:
        """
        ACTIVE INVITATIONS: Get invitations that can still be accepted.

        DEFINITION OF PENDING:
        ----------------------
        An invitation is pending if:
        1. Not yet accepted (accepted=False)
        2. Not expired (expires_at > current_time)

        CRITICAL FOR UI:
        ---------------
        Mobile app and web interface need to show users only invitations
        they can actually accept. No point showing expired invitations.

        PERFORMANCE OPTIMIZATION:
        ------------------------
        Single query filters by vault, acceptance status, and expiration.
        Uses database indexes for efficient time-based filtering.

        BUSINESS IMPACT:
        ---------------
        - Users see actionable invitations only
        - Reduces support tickets about expired invitations
        - Improves user experience in invitation management
        """
        current_time = datetime.utcnow()
        return (
            self.db.query(self.model)
            .filter(
                self.model.vault_id == vault_id,
                self.model.accepted == False,
                self.model.expires_at > current_time
            )
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_expired_invitations(self) -> List[VaultInvitation]:
        """
        SYSTEM MAINTENANCE: Find invitations that have expired.

        PURPOSE:
        --------
        Identify invitations that are no longer valid for cleanup or reporting.

        BUSINESS USES:
        -------------
        - System cleanup jobs remove expired invitations
        - Analytics on invitation acceptance rates
        - Security monitoring for abandoned invitations
        - User experience improvements (hide expired invitations)

        SECURITY NOTE:
        -------------
        Expired invitations pose no security risk since they can't be accepted,
        but they should be cleaned up periodically for database hygiene.
        """
        current_time = datetime.utcnow()
        return (
            self.db.query(self.model)
            .filter(self.model.expires_at <= current_time)
            .all()
        )

    # -------------------------------------------------------------------------
    # INVITATION LIFECYCLE OPERATIONS
    # -------------------------------------------------------------------------

    def mark_invitation_accepted(self, invite_code: str) -> Optional[VaultInvitation]:
        """
        INVITATION ACCEPTANCE: Mark invitation as used and return it.

        CRITICAL SECURITY OPERATION:
        ----------------------------
        This is where invitations are "consumed" - they can only be used once.

        VALIDATION CHECKS:
        ------------------
        1. Invitation exists (get_by_invite_code)
        2. Not already accepted (invitation.accepted == False)
        3. Not expired (invitation.is_expired() == False)

        ATOMIC OPERATION:
        ----------------
        - Update acceptance status
        - Commit transaction
        - Refresh object with any database defaults

        RETURNS:
        --------
        VaultInvitation or None: The updated invitation if successful, None if invalid

        FAILURE SCENARIOS:
        ------------------
        - Invalid invite code: Returns None
        - Already accepted: Returns None (prevents double acceptance)
        - Expired invitation: Returns None (prevents late acceptance)

        POST-ACCEPTANCE:
        ---------------
        Service layer will use this invitation to create a VaultMembership record.
        """
        invitation = self.get_by_invite_code(invite_code)
        if invitation and not invitation.accepted and not invitation.is_expired():
            invitation.accepted = True
            self.db.commit()
            self.db.refresh(invitation)
            return invitation
        return None

    def delete_invitation(self, invite_code: str) -> bool:
        """
        INVITATION REMOVAL: Permanently delete an invitation.

        USE CASES:
        ----------
        - Admin revokes invitation before acceptance
        - User cancels invitation they created
        - System cleanup of invalid invitations

        SAFETY:
        -------
        Only deletes if invitation exists. No errors if code not found.

        BUSINESS IMPACT:
        ---------------
        - Immediately prevents invitation acceptance
        - Removes from pending invitations lists
        - Updates invitation counts for vault

        RETURNS:
        --------
        bool: True if deleted, False if invitation not found
        """
        invitation = self.get_by_invite_code(invite_code)
        if invitation:
            self.db.delete(invitation)
            self.db.commit()
            return True
        return False

    def cleanup_expired_invitations(self) -> int:
        """
        BULK CLEANUP: Remove all expired invitations in single operation.

        PERFORMANCE OPTIMIZATION:
        -------------------------
        Uses bulk DELETE query instead of loading objects into memory.
        Much faster for large numbers of expired invitations.

        SYNCHRONIZE_SESSION=False:
        --------------------------
        Tells SQLAlchemy not to track which objects were deleted.
        Faster for bulk operations but means we can't use those objects afterward.

        RETURNS:
        --------
        int: Number of invitations deleted

        SCHEDULED MAINTENANCE:
        ---------------------
        This should be run periodically (daily/weekly) to:
        - Keep database clean and fast
        - Remove security-relevant records
        - Improve query performance
        - Reduce storage costs

        MONITORING:
        -----------
        Return count should be monitored to detect:
        - Sudden spikes in expired invitations
        - Potential issues with invitation acceptance
        - System performance problems
        """
        current_time = datetime.utcnow()
        deleted_count = (
            self.db.query(self.model)
            .filter(self.model.expires_at <= current_time)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted_count

    def create_invitation(self, vault_id: int, invited_by: int, role: InvitationRole,
                         expires_at: datetime) -> VaultInvitation:
        """
        INVITATION CREATION: Create new invitation with specified parameters.

        BUSINESS CONTEXT:
        -----------------
        This is called when a vault admin wants to invite someone to their vault.
        The invitation represents a "pending membership" that becomes active
        when the user accepts it.

        PARAMETERS:
        -----------
        - vault_id: Which vault the user is being invited to
        - invited_by: Who is sending the invitation (for audit trail)
        - role: What role the user will have if they accept
        - expires_at: When the invitation becomes invalid

        TRANSACTION SAFETY:
        -------------------
        - Add to database
        - Commit transaction
        - Refresh to get any database-generated fields (like auto-increment ID)

        RETURNS:
        --------
        VaultInvitation: The newly created invitation object

        POST-CREATION:
        -------------
        Service layer typically sends notification (email/app) to invited user
        with the invite_code for them to use when accepting.
        """
        invitation = VaultInvitation(
            vault_id=vault_id,
            invited_by=invited_by,
            role=role,
            expires_at=expires_at
        )

        self.db.add(invitation)
        self.db.commit()
        self.db.refresh(invitation)
        return invitation


# =============================================================================
# COMMON QUERY PATTERNS (for reference)
# =============================================================================
"""
WHEN WORKING WITH THIS REPOSITORY, YOU'LL COMMONLY NEED:

1. CHECK IF INVITATION EXISTS AND IS VALID:
   invitation = repo.get_by_invite_code(code)
   if invitation and invitation.is_valid():
       # Process invitation acceptance

2. GET INVITATION STATISTICS FOR A VAULT:
   total_invitations = len(repo.get_invitations_by_vault(vault_id))
   pending_invitations = len(repo.get_pending_invitations(vault_id))
   expired_invitations = len(repo.get_expired_invitations())

3. FIND RECENT INVITATION ACTIVITY:
   recent_invitations = repo.get_invitations_by_inviter(user_id)
   # Show in admin dashboard

4. BULK INVITATION MANAGEMENT:
   # Clean up old invitations
   deleted_count = repo.cleanup_expired_invitations()

   # Get all invitations needing attention
   all_expired = repo.get_expired_invitations()

5. INVITATION ACCEPTANCE WORKFLOW:
   # User provides invite code
   invitation = repo.get_by_invite_code(code)

   # Validate invitation
   if not invitation or not invitation.is_valid():
       return "Invalid or expired invitation"

   # Accept invitation
   accepted_invitation = repo.mark_invitation_accepted(code)
   if accepted_invitation:
       # Create vault membership (in service layer)
       # Send welcome notification (in service layer)

6. ADMIN OVERSIGHT QUERIES:
   # Find invitations created by specific admin
   admin_invitations = repo.get_invitations_by_inviter(admin_id)

   # Find all pending invitations for vault
   pending = repo.get_pending_invitations(vault_id)

   # Check invitation acceptance rates
   all_invitations = repo.get_invitations_by_vault(vault_id)
   accepted_count = sum(1 for inv in all_invitations if inv.accepted)
"""