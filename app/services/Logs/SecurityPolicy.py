from typing import Optional

class SecurityPolicy:
    """
    Manages security policies for authentication, such as dual-factor requirements.
    """
    
    def requires_dual_auth(self, vault_identifier: int | str) -> bool:
        """
        Determine if a vault requires dual-factor authentication.

        Currently hardcoded: Vaults with ID < 100 require dual auth (e.g., high-security).
        In production, query vault config or user permissions for dynamic decision.

        Args:
            vault_identifier (int | str): The vault ID (int) or device_id (str).

        Returns:
            bool: True if dual auth required, False for single-factor.
        """
        # Handle both vault_id (int) and device_id (str)
        if isinstance(vault_identifier, str):
            # For now, use a simple heuristic based on device_id format
            # In production, this should query the vault table
            # For device_id like "SV03", extract the number part
            try:
                vault_number = int(vault_identifier[2:])  # Extract number from "SV03"
                vault_id = vault_number
            except (ValueError, IndexError):
                return False  # Default to single auth if can't parse
        else:
            vault_id = vault_identifier

        # TODO: Query vault model for 'requires_mfa' flag in future
        return vault_id < 100  # Placeholder: low IDs require MFA