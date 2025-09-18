from typing import Optional

class SecurityPolicy:
    """
    Manages security policies for authentication, such as dual-factor requirements.
    """
    
    def requires_dual_auth(self, vault_id: int) -> bool:
        """
        Determine if a vault requires dual-factor authentication.
        
        Currently hardcoded: Vaults with ID < 100 require dual auth (e.g., high-security).
        In production, query vault config or user permissions for dynamic decision.
        
        Args:
            vault_id (int): The ID of the vault.
            
        Returns:
            bool: True if dual auth required, False for single-factor.
        """
        # TODO: Query vault model for 'requires_mfa' flag in future
        return vault_id < 100  # Placeholder: low IDs require MFA