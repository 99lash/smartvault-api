from typing import List
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.models.User import User

class VaultAccessController:
    def __init__(self, vault_membership_repo: VaultMembershipRepository):
        self.vault_membership_repo = vault_membership_repo

    def check_access(self, user_id: int, vault_id: str) -> bool:
        """
        Check if the user has access to the specified vault.

        Args:
            user_id (int): The ID of the user.
            vault_id (int): The ID of the vault.

        Returns:
            bool: True if access granted, False otherwise.
        """
        import logging
        logging.info(f"Vault access check: user_id={user_id}, vault_id={vault_id}")
        users_for_vault: List[User] = self.vault_membership_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        logging.info(f"Vault {vault_id} users IDs: {vault_user_ids}")
        has_access = user_id in vault_user_ids
        logging.info(f"Access granted for user {user_id} to vault {vault_id}: {has_access}")
        return has_access