from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.models.VaultInvitation import VaultInvitation, InvitationRole
from app.repositories.VaultInvitationRepository import VaultInvitationRepository
from app.services.VaultMembershipService import VaultMembershipService

class VaultInvitationService:
    """
    Service layer for vault invitation business logic.

    Handles invitation creation, validation, acceptance, and management
    with proper integration with vault membership system.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = VaultInvitationRepository(db)
        self.membership_service = VaultMembershipService(db)

    def create_invitation(self, vault_id: str, invited_by: int, role: InvitationRole,
                           expires_in_hours: int = 24) -> VaultInvitation:
        """
        Create a new vault invitation.

        Args:
            vault_id (int): The vault to invite the user to
            invited_by (int): The user sending the invitation
            role (InvitationRole): The role to grant when accepted
            expires_in_hours (int): Hours until invitation expires (default: 24)

        Returns:
            VaultInvitation: The created invitation
        """
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        return self.repo.create_invitation(
            vault_id=vault_id,
            invited_by=invited_by,
            role=role,
            expires_at=expires_at
        )

    def accept_invitation(self, invite_code: str) -> Optional[VaultInvitation]:
        """
        Accept a vault invitation and create membership.

        Args:
            invite_code (str): The invitation code to accept

        Returns:
            VaultInvitation | None: The invitation if accepted successfully
        """
        invitation = self.repo.get_by_invite_code(invite_code)

        if not invitation:
            raise ValueError("Invitation not found")

        if invitation.accepted:
            raise ValueError("Invitation already accepted")

        if invitation.is_expired():
            raise ValueError("Invitation has expired")

        # Mark invitation as accepted
        accepted_invitation = self.repo.mark_invitation_accepted(invite_code)

        if accepted_invitation:
            # Create the vault membership
            try:
                self.membership_service.add_user_to_vault(
                    user_id=accepted_invitation.invited_by,  # This should be the accepting user
                    vault_id=accepted_invitation.vault_id,
                    role=accepted_invitation.role
                )
            except Exception as e:
                # If membership creation fails, revert invitation acceptance
                accepted_invitation.accepted = False
                self.db.commit()
                raise ValueError(f"Failed to create vault membership: {str(e)}")

        return accepted_invitation

    def get_invitation_by_code(self, invite_code: str) -> Optional[VaultInvitation]:
        """Get invitation details by invite code"""
        return self.repo.get_by_invite_code(invite_code)

    def get_vault_invitations(self, vault_id: str) -> List[VaultInvitation]:
        """Get all invitations for a vault"""
        return self.repo.get_invitations_by_vault(vault_id)

    def get_pending_invitations(self, vault_id: str) -> List[VaultInvitation]:
        """Get all pending invitations for a vault"""
        return self.repo.get_pending_invitations(vault_id)

    def delete_invitation(self, invite_code: str) -> bool:
        """Delete an invitation by invite code"""
        return self.repo.delete_invitation(invite_code)

    def cleanup_expired_invitations(self) -> int:
        """Clean up all expired invitations"""
        return self.repo.cleanup_expired_invitations()

    def generate_invite_link(self, invitation: VaultInvitation) -> str:
        """Generate a shareable invite link"""
        base_url = "https://yourapp.com"  # Configure this appropriately
        return f"{base_url}/invite/{invitation.invite_code}"

    def validate_invitation_for_acceptance(self, invite_code: str) -> dict:
        """
        Validate if an invitation can be accepted.

        Returns:
            dict: Validation result with status and message
        """
        invitation = self.repo.get_by_invite_code(invite_code)

        if not invitation:
            return {
                "valid": False,
                "reason": "Invitation not found",
                "expired": False,
                "accepted": False
            }

        return {
            "valid": invitation.is_valid(),
            "reason": "Invitation is valid and can be accepted" if invitation.is_valid() else
                     "Invitation expired" if invitation.is_expired() else "Invitation already accepted",
            "expired": invitation.is_expired(),
            "accepted": invitation.accepted,
            "vault_id": invitation.vault_id,
            "role": invitation.role.value,
            "expires_at": invitation.expires_at.isoformat()
        }