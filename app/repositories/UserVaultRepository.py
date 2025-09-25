from sqlalchemy.orm import Session
from app.models.UserVault import UserVault
from app.models.User import User
from app.models.Vault import Vault
from app.repositories.Repository import Repository

class UserVaultRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, UserVault)

    def get_by_user_and_vault(self, user_id: int, vault_id: int):
        if not isinstance(user_id, int) or not isinstance(vault_id, int) or user_id <= 0 or vault_id <= 0:
            raise ValueError("Invalid user_id or vault_id")

        return (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id, self.model.vault_id == vault_id)
            .first()
        )

    def get_vaults_for_user(self, user_id: int):
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")

        return (
            self.db.query(Vault)
            .join(self.model)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_users_for_vault(self, vault_id: int):
        if not isinstance(vault_id, int) or vault_id <= 0:
            raise ValueError("Invalid vault_id")

        try:
            users = (
                self.db.query(User)
                .join(UserVault, User.id == UserVault.user_id)
                .filter(UserVault.vault_id == vault_id)
                .all()
            )
            return users
        except Exception as e:
            # Don't log sensitive information, just log error type
            import logging
            logging.error(f"Database error in get_users_for_vault: {type(e).__name__}")
            raise

    def has_access(self, user_id: int, vault_id: int):
        if not isinstance(user_id, int) or not isinstance(vault_id, int) or user_id <= 0 or vault_id <= 0:
            return False

        return self.get_by_user_and_vault(user_id, vault_id) is not None

    def get_users_sharing_vault_access(self, user_id: int):
        """
        Get all users who share vault access with the specified user.
        Uses a subquery to find users who have access to the same vaults.

        Args:
            user_id: The user ID to find shared vault access for

        Returns:
            List of User objects who share at least one vault with the specified user

        Raises:
            ValueError: If user_id is invalid
            HTTPException: If database error occurs
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("Invalid user_id")

        try:
            # First, get all vaults that the specified user has access to
            user_vaults_subquery = (
                self.db.query(UserVault.vault_id)
                .filter(UserVault.user_id == user_id)
                .subquery()
            )

            # Then, find all users who have access to those same vaults (excluding the user themselves)
            shared_users = (
                self.db.query(User)
                .join(UserVault, User.id == UserVault.user_id)
                .filter(UserVault.vault_id.in_(user_vaults_subquery))
                .filter(User.id != user_id)  # Exclude the user themselves
                .distinct()
                .all()
            )

            return shared_users
        except Exception as e:
            # Don't log sensitive information, just log error type
            import logging
            logging.error(f"Database error in get_users_sharing_vault_access: {type(e).__name__}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail="Database error occurred")