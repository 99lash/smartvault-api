from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.models.VaultMembership import VaultMembership, MembershipRole
from .Repository import Repository

class VaultMembershipRepository(Repository):
    """
    Repository for VaultMembership operations.

    Handles database operations for vault membership management including
    role-based access control within vaults.
    """
    def __init__(self, db: Session):
        super().__init__(db, VaultMembership)

    def get_by_user_and_vault(self, user_id: int, vault_id: int) -> Optional[VaultMembership]:
        """Get membership record for a specific user-vault pair"""
        return (
            self.db.query(self.model)
            .filter(
                self.model.user_id == user_id,
                self.model.vault_id == vault_id
            )
            .first()
        )

    def get_user_memberships(self, user_id: int) -> List[VaultMembership]:
        """Get all vault memberships for a specific user"""
        return (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_vault_memberships(self, vault_id: int) -> List[VaultMembership]:
        """Get all memberships for a specific vault"""
        return (
            self.db.query(self.model)
            .filter(self.model.vault_id == vault_id)
            .all()
        )

    def get_memberships_by_role(self, vault_id: int, role: MembershipRole) -> List[VaultMembership]:
        """Get all memberships for a vault with a specific role"""
        return (
            self.db.query(self.model)
            .filter(
                self.model.vault_id == vault_id,
                self.model.role == role
            )
            .all()
        )

    def user_has_role_in_vault(self, user_id: int, vault_id: int, role: MembershipRole) -> bool:
        """Check if a user has a specific role in a vault"""
        membership = self.get_by_user_and_vault(user_id, vault_id)
        return membership is not None and membership.role == role

    def promote_user_in_vault(self, user_id: int, vault_id: int, new_role: MembershipRole) -> Optional[VaultMembership]:
        """Promote or demote a user's role in a vault"""
        membership = self.get_by_user_and_vault(user_id, vault_id)
        if membership:
            membership.role = new_role
            membership.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(membership)
            return membership
        return None

    def remove_user_from_vault(self, user_id: int, vault_id: int) -> bool:
        """Remove a user's membership from a vault"""
        membership = self.get_by_user_and_vault(user_id, vault_id)
        if membership:
            self.db.delete(membership)
            self.db.commit()
            return True
        return False

    def get_vaults_for_user(self, user_id: int):
        """Get all vaults accessible to a user"""
        from app.models.Vault import Vault
        return (
            self.db.query(Vault)
            .join(self.model, Vault.id == self.model.vault_id)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_users_for_vault(self, vault_id: int):
        """Get all users with access to a vault"""
        from app.models.User import User
        return (
            self.db.query(User)
            .join(self.model, User.id == self.model.user_id)
            .filter(self.model.vault_id == vault_id)
            .filter(User.deleted_at == None)  # Exclude soft-deleted users
            .all()
        )

    def get_users_sharing_vault_access(self, user_id: int):
        """
        Get all users who share vault access with the specified user.
        Uses a subquery to find users who have access to the same vaults.

        Args:
            user_id: The user ID to find shared vault access for

        Returns:
            List of User objects who share at least one vault with the specified user
        """
        from app.models.User import User

        # First, get all vault IDs that the specified user has access to
        user_vaults_subquery = (
            self.db.query(self.model.vault_id)
            .filter(self.model.user_id == user_id)
            .subquery()
        )

        # Then, find all users who have access to those same vaults (excluding the user themselves)
        shared_users = (
            self.db.query(User)
            .join(self.model, User.id == self.model.user_id)
            .filter(self.model.vault_id.in_(user_vaults_subquery))
            .filter(User.id != user_id)  # Exclude the user themselves
            .distinct()
            .all()
        )

        return shared_users