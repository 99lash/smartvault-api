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

    def validate_credential(self, credential: str, is_nfc: bool) -> tuple[Optional[int], Optional[str]]:
        """
        Validate a single NFC or PIN credential against the database.
        
        Performs a quick lookup to retrieve the associated user ID if valid.
        
        Args:
            credential (str): The credential value (UID or PIN code).
            is_nfc (bool): True if NFC credential, False if PIN.
            
        Returns:
            tuple[Optional[int], Optional[str]]: (user_id, method_string) if valid, (None, None) otherwise.
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

    def extract_user_id_from_details(self, details: str) -> Optional[int]:
        """
        Extract user_id from credential details without full validation.
        
        This is a lightweight lookup used to quickly check for existing MFA sessions
        before full validation. It parses details and queries the DB minimally.
        
        Args:
            details (str): Authentication details string.
            
        Returns:
            Optional[int]: User ID if found, None otherwise.
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