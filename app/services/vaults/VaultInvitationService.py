from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.VaultInvitation import VaultInvitation, InvitationRole
from app.models.VaultMembership import MembershipRole
from app.repositories.VaultInvitationRepository import VaultInvitationRepository
from app.services.vaults.VaultMembershipService import VaultMembershipService


# =============================================================================
# VAULT INVITATION SERVICE CLASS
# =============================================================================

class VaultInvitationService:
   
    def __init__(self, db: Session):
        self.db = db
        self.invitation_repo = VaultInvitationRepository(db)
        self.membership_service = VaultMembershipService(db)

    # -------------------------------------------------------------------------
    # CORE BUSINESS OPERATION
    # -------------------------------------------------------------------------

    def accept_invitation(self, invite_code: str, user_id: int) -> VaultInvitation:
        # =====================================================================
        # STEP 1: VALIDATE INVITATION STATE
        # =====================================================================
        invitation = self.invitation_repo.get_by_invite_code(invite_code)

        if not invitation:
            raise ValueError("Invalid invitation code")
        if invitation.is_expired():
            raise ValueError("Invitation has expired")
        if invitation.accepted:
            raise ValueError("Invitation already accepted")

        # =====================================================================
        # STEP 2: ACCEPT INVITATION AND CREATE MEMBERSHIP
        # =====================================================================
        try:
            # Mark invitation as accepted with timestamp
            invitation.accepted = True
            # Note: accepted_at field would need to be added to VaultInvitation model
            # invitation.accepted_at = datetime.utcnow()

            # Create vault membership with the role specified in invitation
            # This ensures role consistency between invitation and membership
            self.membership_service.add_user_to_vault(
                user_id=user_id,
                vault_id=invitation.vault_id,
                role=MembershipRole(invitation.role.value)  # Convert enum to MembershipRole
            )

            # =================================================================
            # STEP 3: COMMIT CHANGES AND REFRESH
            # =================================================================
            # Explicitly commit the transaction to ensure changes are persisted
            self.db.commit()

            # Refresh invitation object to get any database-generated updates
            self.db.refresh(invitation)
            return invitation

        except Exception as e:
            # =================================================================
            # STEP 4: ERROR HANDLING AND ROLLBACK
            # =================================================================
            # Rollback any uncommitted changes on error
            self.db.rollback()

            # Convert technical database errors to user-friendly messages
            # while preserving the original error for debugging
            raise ValueError(f"Failed to accept invitation: {str(e)}")

    # -------------------------------------------------------------------------
    # INVITATION CREATION OPERATION
    # -------------------------------------------------------------------------

    def create_invitation(self, vault_id: int, invited_by: int, role: InvitationRole,
                         expires_in_hours: int) -> VaultInvitation:
        # =====================================================================
        # STEP 1: VALIDATE INVITER PERMISSIONS
        # =====================================================================
        if not self.membership_service.is_user_admin_of_vault(invited_by, vault_id):
            raise ValueError("Only vault administrators can create invitations")

        # =====================================================================
        # STEP 2: CALCULATE EXPIRATION TIME
        # =====================================================================
        from datetime import timedelta
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        # =====================================================================
        # STEP 3: CREATE INVITATION VIA REPOSITORY
        # =====================================================================
        try:
            invitation = self.invitation_repo.create_invitation(
                vault_id=vault_id,
                invited_by=invited_by,
                role=role,
                expires_at=expires_at
            )

            # Ensure the invitation is committed to the database
            self.db.commit()
            return invitation

        except Exception as e:
            # =================================================================
            # STEP 4: ERROR HANDLING AND ROLLBACK
            # =================================================================
            # Rollback any uncommitted changes on error
            self.db.rollback()

            # Convert technical database errors to user-friendly messages
            raise ValueError(f"Failed to create invitation: {str(e)}")

    # -------------------------------------------------------------------------
    # INVITATION LOOKUP OPERATIONS
    # -------------------------------------------------------------------------

    def get_invitation_by_code(self, invite_code: str) -> Optional[VaultInvitation]:
        return self.invitation_repo.get_by_invite_code(invite_code)

    def get_vault_invitations(self, vault_id: int) -> List[VaultInvitation]:
        return self.invitation_repo.get_invitations_by_vault(vault_id)

    def validate_invitation_for_acceptance(self, invite_code: str) -> dict:
        invitation = self.get_invitation_by_code(invite_code)

        if not invitation:
            return {
                'valid': False,
                'reason': 'Invitation not found'
            }

        if invitation.is_expired():
            return {
                'valid': False,
                'reason': 'Invitation has expired'
            }

        if invitation.accepted:
            return {
                'valid': False,
                'reason': 'Invitation already accepted'
            }

        return {
            'valid': True,
            'reason': 'Invitation is valid and ready for acceptance'
        }

    def delete_invitation(self, invite_code: str) -> bool:
        try:
            result = self.invitation_repo.delete_invitation(invite_code)
            if result:
                self.db.commit()
            return result
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to delete invitation: {str(e)}")

    def cleanup_expired_invitations(self) -> int:
        try:
            deleted_count = self.invitation_repo.cleanup_expired_invitations()
            self.db.commit()
            return deleted_count
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to cleanup expired invitations: {str(e)}")
