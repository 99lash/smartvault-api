from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.models.VaultInvitation import VaultInvitation, InvitationRole
from .Repository import Repository

class VaultInvitationRepository(Repository):
    """
    Repository for VaultInvitation operations.

    Handles database operations for vault invitation management including
    invitation creation, validation, acceptance, and cleanup.
    """

    def __init__(self, db: Session):
        super().__init__(db, VaultInvitation)

    def get_by_invite_code(self, invite_code: str) -> Optional[VaultInvitation]:
        """Get invitation by its unique invite code"""
        return (
            self.db.query(self.model)
            .filter(self.model.invite_code == invite_code)
            .first()
        )

    def get_invitations_by_vault(self, vault_id: int) -> List[VaultInvitation]:
        """Get all invitations for a specific vault"""
        return (
            self.db.query(self.model)
            .filter(self.model.vault_id == vault_id)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_invitations_by_inviter(self, invited_by: int) -> List[VaultInvitation]:
        """Get all invitations sent by a specific user"""
        return (
            self.db.query(self.model)
            .filter(self.model.invited_by == invited_by)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_pending_invitations(self, vault_id: int) -> List[VaultInvitation]:
        """Get all pending (not accepted and not expired) invitations for a vault"""
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
        """Get all expired invitations"""
        current_time = datetime.utcnow()
        return (
            self.db.query(self.model)
            .filter(self.model.expires_at <= current_time)
            .all()
        )

    def mark_invitation_accepted(self, invite_code: str) -> Optional[VaultInvitation]:
        """Mark an invitation as accepted"""
        invitation = self.get_by_invite_code(invite_code)
        if invitation and not invitation.accepted and not invitation.is_expired():
            invitation.accepted = True
            self.db.commit()
            self.db.refresh(invitation)
            return invitation
        return None

    def delete_invitation(self, invite_code: str) -> bool:
        """Delete an invitation by invite code"""
        invitation = self.get_by_invite_code(invite_code)
        if invitation:
            self.db.delete(invitation)
            self.db.commit()
            return True
        return False

    def cleanup_expired_invitations(self) -> int:
        """Delete all expired invitations and return count of deleted records"""
        expired_invitations = self.get_expired_invitations()
        deleted_count = 0

        for invitation in expired_invitations:
            self.db.delete(invitation)
            deleted_count += 1

        if deleted_count > 0:
            self.db.commit()

        return deleted_count

    def create_invitation(self, vault_id: int, invited_by: int, role: InvitationRole,
                         expires_at: datetime) -> VaultInvitation:
        """Create a new vault invitation"""
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