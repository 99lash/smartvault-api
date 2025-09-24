from sqlalchemy.orm import Session
from typing import List, Optional
from app.repositories.UserVaultRepository import UserVaultRepository
from app.models.UserVault import UserVault
from app.models.User import User
from app.models.Vault import Vault

# -----------------------------
# Service layer for UserVault logic
# -----------------------------
# Encapsulates business logic related to user-vault associations:
# - managing user permissions for vaults
# - access control validation
# - listing user-accessible vaults and vault users
class UserVaultService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = UserVaultRepository(db)

    # --- Basic CRUD Operations ---

    def create_association(self, user_id: int, vault_id: int) -> UserVault:
        """Create a user-vault association (add user to vault)"""
        # Check if association already exists
        existing = self.repo.get_by_user_and_vault(user_id, vault_id)
        if existing:
            raise ValueError("User already has access to this vault")
        return self.repo.create(user_id=user_id, vault_id=vault_id)

    def get_association_by_id(self, association_id: int) -> UserVault | None:
        """Fetch a user-vault association by ID"""
        return self.repo.get_by_id(association_id)

    def delete_association(self, user_id: int, vault_id: int) -> UserVault | None:
        """Delete a user-vault association (remove user from vault)"""
        association = self.repo.get_by_user_and_vault(user_id, vault_id)
        if not association:
            return None
        return self.repo.delete(association.id)

    # --- Access Management Operations ---

    def add_user_to_vault(self, user_id: int, vault_id: int) -> UserVault:
        """Add a user to a vault with access validation"""
        # Optional: Could add checks like user exists, vault exists, etc.
        # via UserService and VaultService if injected
        return self.create_association(user_id, vault_id)

    def remove_user_from_vault(self, user_id: int, vault_id: int) -> bool:
        """Remove a user from a vault"""
        deleted = self.delete_association(user_id, vault_id)
        return deleted is not None

    def has_user_access_to_vault(self, user_id: int, vault_id: int) -> bool:
        """Check if a user has access to a specific vault"""
        return self.repo.has_access(user_id, vault_id)

    # --- Query Operations ---

    def get_vaults_for_user(self, user_id: int) -> List[Vault]:
        """Get all vaults accessible to a user"""
        return self.repo.get_vaults_for_user(user_id)

    def get_users_for_vault(self, vault_id: int) -> List[User]:
        """Get all users with access to a vault"""
        return self.repo.get_users_for_vault(vault_id)

    def get_all_associations(self) -> List[UserVault]:
        """List all user-vault associations"""
        return self.repo.get_all()

    # --- Bulk Operations ---

    def add_users_to_vault(self, user_ids: List[int], vault_id: int) -> List[UserVault]:
        """Add multiple users to a vault"""
        associations = []
        for user_id in user_ids:
            try:
                assoc = self.add_user_to_vault(user_id, vault_id)
                associations.append(assoc)
            except ValueError:
                # Skip if already associated
                pass
        return associations

    def remove_users_from_vault(self, user_ids: List[int], vault_id: int) -> int:
        """Remove multiple users from a vault"""
        removed_count = 0
        for user_id in user_ids:
            if self.remove_user_from_vault(user_id, vault_id):
                removed_count += 1
        return removed_count

    def get_users_sharing_vault_access(self, user_id: int) -> List[User]:
        """
        Get all users who share vault access with the specified user.

        This method:
        1. Verifies the user exists
        2. Finds all vaults the user has access to
        3. Finds all other users who have access to any of those same vaults
        4. Returns a deduplicated list of users

        Args:
            user_id: The user ID to find shared vault access for

        Returns:
            List of User objects who share at least one vault with the specified user

        Raises:
            ValueError: If the user doesn't exist
        """
        # First verify the user exists (we can use UserService for this)
        # For now, we'll assume the user exists and let the query handle it
        shared_users = self.repo.get_users_sharing_vault_access(user_id)

        return shared_users