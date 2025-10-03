from typing import Optional
from app.repositories.NfcCardRepository import NfcCardRepository
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
import json

class CredentialValidator:
    def __init__(self, nfc_repo: NfcCardRepository, pin_repo: KeypadPinsRepository):
        self.nfc_repo = nfc_repo
        self.pin_repo = pin_repo

    def parse_credentials(self, details: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse authentication details to extract NFC UID and/or PIN code.
        
        Supports modern JSON format (e.g., {"nfc": "uid", "pin": "code"}) and legacy string formats
        (e.g., "NFC:uid", "PIN:code", raw UID/PIN). Handles parsing errors gracefully.
        
        Args:
            details (str): Raw authentication details string.
            
        Returns:
            tuple[Optional[str], Optional[str]]: (nfc_uid, pin_code) - Extracted values or None if not present.
        """
        nfc = None
        pin = None
        
        try:
            # Attempt to parse as JSON (preferred modern format)
            data = json.loads(details)
            if isinstance(data, dict):
                # Standard JSON object with explicit keys
                nfc = data.get('nfc')
                pin = data.get('pin')
            else:
                # JSON parsed to primitive - treat as legacy string
                legacy_value = str(data)
                if legacy_value.startswith('NFC:'):
                    nfc = legacy_value[4:]  # Strip prefix
                elif legacy_value.startswith('PIN:'):
                    pin = legacy_value[4:]  # Strip prefix
                elif ':' in legacy_value:
                    # Colon-separated UID (legacy NFC format)
                    nfc = legacy_value
                elif legacy_value.isdigit() and 4 <= len(legacy_value) <= 6:
                    # Numeric string of PIN length - assume PIN
                    pin = legacy_value
                else:
                    raise ValueError("Invalid format")
                    
        except (json.JSONDecodeError, ValueError):
            # Fallback to direct string parsing for non-JSON inputs
            if details.startswith('NFC:'):
                nfc = details[4:]  # Strip "NFC:" prefix
            elif details.startswith('PIN:'):
                pin = details[4:]  # Strip "PIN:" prefix
            elif ':' in details:
                # Assume colon-separated is NFC UID
                nfc = details
            elif details.isdigit() and 4 <= len(details) <= 6:
                # Plain numeric of PIN length
                pin = details
                
        return nfc, pin

    def validate_credential_for_vault(self, credential: str, is_nfc: bool, vault_id: str, access_controller) -> tuple[Optional[int], Optional[str]]:
        """
        Validate a credential against users who have access to a specific vault.
        This is the vault-centric approach.

        Args:
            credential (str): The credential value (UID or PIN code).
            is_nfc (bool): True if NFC credential, False if PIN.
            vault_id (int): The vault ID to check access for.
            access_controller: VaultAccessController instance to check permissions.

        Returns:
            tuple[Optional[int], Optional[str]]: (user_id, method_string) if valid for vault, (None, None) otherwise.
        """
        if is_nfc:
            # Validate NFC card by UID
            card = self.nfc_repo.get_by_uid(credential)
            if card and card.user_id:
                # Check if this NFC user has vault access
                has_access = access_controller.check_access(card.user_id, vault_id)
                if has_access:
                    return card.user_id, f"NFC: {credential}"
        else:
            # Validate PIN code - check against all users who have vault access
            authorized_users = access_controller.vault_membership_repo.get_users_for_vault(vault_id)
            authorized_user_ids = [user.id for user in authorized_users]

            # Check if PIN belongs to any authorized user
            for user_id in authorized_user_ids:
                user_pin = self.pin_repo.get_by_user_and_pin(user_id, credential)
                if user_pin:
                    return user_id, f"PIN: {credential}"

        return None, None

    def validate_credential(self, credential: str, is_nfc: bool) -> tuple[Optional[int], Optional[str]]:
        """
        Legacy method - kept for backward compatibility.
        Use validate_credential_for_vault() for new vault-centric approach.
        """
        if is_nfc:
            # Validate NFC card by UID
            card = self.nfc_repo.get_by_uid(credential)
            if card and card.user_id:
                return card.user_id, f"NFC: {credential}"
        else:
            # Validate PIN code
            record = self.pin_repo.get_by_pin_code(credential)
            if record and record.user_id:
                return record.user_id, f"PIN: {credential}"
        return None, None

    def extract_user_id_from_details_for_vault(self, details: str, vault_id: str, access_controller) -> Optional[int]:
        """
        Extract user_id from credential details using vault-centric approach.

        This is a lightweight lookup used to quickly check for existing MFA sessions
        before full validation. Only returns user_id if the credential belongs to
        a user authorized for the specified vault.

        Args:
            details (str): Authentication details string.
            vault_id (int): The vault ID to check access for.
            access_controller: VaultAccessController instance.

        Returns:
            Optional[int]: User ID if found and authorized for vault, None otherwise.
        """
        try:
            nfc, pin = self.parse_credentials(details)

            # Quick user lookup - prioritize NFC, then PIN
            if nfc:
                user_id, _ = self.validate_credential_for_vault(nfc, True, vault_id, access_controller)
                if user_id:
                    return user_id

            if pin:
                user_id, _ = self.validate_credential_for_vault(pin, False, vault_id, access_controller)
                if user_id:
                    return user_id

            return None
        except Exception:
            # Swallow exceptions to ensure quick failure for session check
            return None

    def extract_user_id_from_details(self, details: str) -> Optional[int]:
        """
        Legacy method - kept for backward compatibility.
        Use extract_user_id_from_details_for_vault() for new vault-centric approach.
        """
        try:
            nfc, pin = self.parse_credentials(details)

            # Quick user lookup - prioritize NFC, then PIN
            if nfc:
                user_id, _ = self.validate_credential(nfc, True)
                if user_id:
                    return user_id

            if pin:
                user_id, _ = self.validate_credential(pin, False)
                if user_id:
                    return user_id

            return None
        except Exception:
            # Swallow exceptions to ensure quick failure for session check
            return None