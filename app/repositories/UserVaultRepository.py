from sqlalchemy.orm import Session
from app.models.UserVault import UserVault
from app.models.User import User
from app.models.Vault import Vault
from app.repositories.Repository import Repository

class UserVaultRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, UserVault)

    def get_by_user_and_vault(self, user_id: int, vault_id: int):
        return (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id, self.model.vault_id == vault_id)
            .first()
        )

    def get_vaults_for_user(self, user_id: int):
        return (
            self.db.query(Vault)
            .join(self.model)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_users_for_vault(self, vault_id: int):
        import logging
        query = (
            self.db.query(User)
            .join(UserVault, User.id == UserVault.user_id)
            .filter(UserVault.vault_id == vault_id)
        )
        logging.info(f"get_users_for_vault query for vault {vault_id}: {str(query)}")
        users = query.all()
        user_ids = [u.id for u in users]
        logging.info(f"get_users_for_vault for vault {vault_id}: found {len(users)} users, IDs: {user_ids}")
        return users

    def has_access(self, user_id: int, vault_id: int):
        return self.get_by_user_and_vault(user_id, vault_id) is not None

    def get_users_sharing_vault_access(self, user_id: int):
        """
        Get all users who share vault access with the specified user.
        This finds all vaults the user has access to, then finds all other users
        who have access to any of those same vaults.

        Args:
            user_id: The user ID to find shared vault access for

        Returns:
            List of User objects who share at least one vault with the specified user
        """
        # First, get all vaults the user has access to
        user_vaults = self.get_vaults_for_user(user_id)

        if not user_vaults:
            return []

        # Get vault IDs
        vault_ids = [vault.id for vault in user_vaults]

        # Find all users who have access to any of these vaults (excluding the original user)
        shared_users = (
            self.db.query(User)
            .join(UserVault, User.id == UserVault.user_id)
            .filter(UserVault.vault_id.in_(vault_ids))
            .filter(User.id != user_id)  # Exclude the original user
            .distinct()  # Remove duplicates
            .all()
        )

        return shared_users 