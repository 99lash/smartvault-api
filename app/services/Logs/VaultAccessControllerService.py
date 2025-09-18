from typing import List
from app.repositories.UserVaultRepository import UserVaultRepository
from app.models.User import User

class VaultAccessController:
    def __init__(self, user_vault_repo: UserVaultRepository):
        self.user_vault_repo = user_vault_repo

    def check_access(self, user_id: int, vault_id: int) -> bool:
        """
        Check if the user has access to the specified vault.
        
        Args:
            user_id (int): The ID of the user.
            vault_id (int): The ID of the vault.
            
        Returns:
            bool: True if access granted, False otherwise.
        """
        users_for_vault: List[User] = self.user_vault_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        return user_id in vault_user_ids