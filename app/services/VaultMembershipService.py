from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.VaultMembership import VaultMembership, MembershipRole
from app.repositories.VaultMembershipRepository import VaultMembershipRepository

class VaultMembershipService:
    """
    Service layer for vault membership business logic.

    Handles role-based access control operations within vaults,
    including membership management, role assignments, and permission checks.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = VaultMembershipRepository(db)

    def add_user_to_vault(self, user_id: int, vault_id: str, role: MembershipRole = MembershipRole.member) -> VaultMembership:
        """Add a user to a vault with specified role"""
        # Check if membership already exists
        existing = self.repo.get_by_user_and_vault(user_id, vault_id)
        if existing:
            raise ValueError(f"User {user_id} is already a member of vault {vault_id}")

        membership = VaultMembership(
            user_id=user_id,
            vault_id=vault_id,
            role=role
        )

        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def remove_user_from_vault(self, user_id: int, vault_id: str) -> bool:
        """Remove a user from a vault"""
        return self.repo.remove_user_from_vault(user_id, vault_id)

    def change_user_role(self, user_id: int, vault_id: str, new_role: MembershipRole) -> Optional[VaultMembership]:
        """Change a user's role in a vault"""
        return self.repo.promote_user_in_vault(user_id, vault_id, new_role)

    def get_user_role_in_vault(self, user_id: int, vault_id: str) -> Optional[MembershipRole]:
        """Get a user's role in a specific vault"""
        membership = self.repo.get_by_user_and_vault(user_id, vault_id)
        return membership.role if membership else None

    def user_has_role_in_vault(self, user_id: int, vault_id: str, role: MembershipRole) -> bool:
        """Check if user has specific role in vault"""
        return self.repo.user_has_role_in_vault(user_id, vault_id, role)

    def get_vault_members(self, vault_id: str) -> List[VaultMembership]:
        """Get all members of a vault"""
        return self.repo.get_vault_memberships(vault_id)

    def get_user_vaults(self, user_id: int) -> List[VaultMembership]:
        """Get all vaults a user is a member of"""
        return self.repo.get_user_memberships(user_id)

    def get_vault_admins(self, vault_id: str) -> List[VaultMembership]:
        """Get all admin members of a vault"""
        return self.repo.get_memberships_by_role(vault_id, MembershipRole.admin)

    def is_user_admin_of_vault(self, user_id: int, vault_id: str) -> bool:
        """Check if user is an admin of the vault"""
        return self.user_has_role_in_vault(user_id, vault_id, MembershipRole.admin)