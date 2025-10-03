from typing import Dict, Optional
import time

class SessionManager:
    auth_sessions: Dict[str, Dict] = {}

    def get_session_key(self, vault_id: str, user_id: int) -> str:
        """
        Generate a unique session key for tracking multi-factor authentication state.
        
        The key combines vault and user IDs to isolate sessions per vault-user pair.
        
        Args:
            vault_id (int): The ID of the vault being accessed.
            user_id (int): The ID of the authenticating user.
            
        Returns:
            str: A formatted session key (e.g., "vault_1_user_123").
        """
        return f"vault_{vault_id}_user_{user_id}"

    def cleanup_expired_sessions(self, timeout_seconds: int = 30):
        """
        Remove expired authentication sessions from the shared session store.
        
        Sessions expire after a configurable timeout to prevent indefinite pending states.
        This is called before each authentication attempt to maintain clean state.
        
        Args:
            timeout_seconds (int): Timeout in seconds (default: 30).
        """
        current_time = time.time()
        expired_keys = [
            key for key, session in SessionManager.auth_sessions.items()
            if current_time - session.get('timestamp', 0) > timeout_seconds
        ]
        for key in expired_keys:
            del SessionManager.auth_sessions[key]

    def clear_sessions_for_vault(self, vault_id: str):
        """
        Clear all authentication sessions for a specific vault.

        Used to reset MFA state on failures, tampers, or security events.

        Args:
            vault_id (int): The vault ID to clear sessions for.
        """
        keys_to_delete = [key for key in SessionManager.auth_sessions if f"vault_{vault_id}_" in key]
        for key in keys_to_delete:
            del SessionManager.auth_sessions[key]

    def find_user_for_vault_session(self, vault_id: str, details: str, validator) -> Optional[int]:
        """
        Find user_id for a vault session using vault-centric credential validation.

        Args:
            vault_id (int): The vault ID.
            details (str): Authentication details.
            validator: CredentialValidator instance.

        Returns:
            Optional[int]: User ID if found and authorized for vault, None otherwise.
        """
        from app.services.Logs.VaultAccessControllerService import VaultAccessController
        from app.repositories.VaultMembershipRepository import VaultMembershipRepository
        from app.core.database import SessionLocal

        db = SessionLocal()
        try:
            vault_membership_repo = VaultMembershipRepository(db)
            controller = VaultAccessController(vault_membership_repo)
            return validator.extract_user_id_from_details_for_vault(details, vault_id, controller)
        finally:
            db.close()