from typing import List
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.models.User import User

class VaultAccessController:
    def __init__(self, vault_membership_repo: VaultMembershipRepository):
        self.vault_membership_repo = vault_membership_repo

    def check_access(self, user_id: int, vault_identifier: int | str) -> bool:
        """
        Check if the user has access to the specified vault.

        Args:
            user_id (int): The ID of the user.
            vault_identifier (int | str): The vault ID (int) or device_id (str).

        Returns:
            bool: True if access granted, False otherwise.
        """
        import logging

        # Handle both vault_id (int) and device_id (str)
        if isinstance(vault_identifier, str):
            # If device_id is provided, we need to look up the vault_id
            from app.repositories.VaultRepository import VaultRepository
            vault_repo = VaultRepository(self.vault_membership_repo.db)
            vault = vault_repo.get_by_device_id(vault_identifier)
            if not vault:
                logging.warning(f"No vault found for device_id: {vault_identifier}")
                return False
            vault_id = vault.id
            logging.info(f"Vault access check: user_id={user_id}, device_id={vault_identifier}, resolved_vault_id={vault_id}")
        else:
            vault_id = vault_identifier
            logging.info(f"Vault access check: user_id={user_id}, vault_id={vault_id}")

        users_for_vault: List[User] = self.vault_membership_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        logging.info(f"Vault {vault_id} users IDs: {vault_user_ids}")
        has_access = user_id in vault_user_ids
        logging.info(f"Access granted for user {user_id} to vault {vault_id}: {has_access}")
        return has_access