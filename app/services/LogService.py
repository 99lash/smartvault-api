from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from app.repositories.LogRepository import LogRepository
from app.repositories.UserVaultRepository import UserVaultRepository
from app.repositories.NfcCardRepository import NfcCardRepository
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
from app.models.Log import Log, LogEventType
import json
import time

# -----------------------------
# Service layer for Log logic
# -----------------------------
# Encapsulates business logic related to logging:
# - audit trail management
# - security event monitoring
# - log analysis and reporting
class LogService:
    auth_sessions: Dict[str, Dict] = {}

    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = LogRepository(db)
        self.user_vault_repo = UserVaultRepository(db)
        self.nfc_repo = NfcCardRepository(db)
        self.pin_repo = KeypadPinsRepository(db)
    # -------------------------------2 auth--------------------------------
    def get_session_key(self, vault_id: int, user_id: int) -> str:
        """Generate session key for tracking multi-factor auth"""
        return f"vault_{vault_id}_user_{user_id}"
    def cleanup_expired_sessions(self, timeout_seconds: int = 30):
        """Remove expired authentication sessions"""
        current_time = time.time()
        expired_keys = [
            key for key, session in LogService.auth_sessions.items()
            if current_time - session.get('timestamp', 0) > timeout_seconds
        ]
        for key in expired_keys:
            del LogService.auth_sessions[key]
    def validate_progressive_access(self, vault_id: int, details: str) -> tuple[Log | None, str]:
        """
        Progressive authentication that builds up factors and can operate in multiple modes:
        1. Single auth mode: First valid credential grants access
        2. Dual auth mode: Requires both NFC and PIN from same user
        3. Mixed mode: Server decides based on vault configuration
        
        Returns:
            tuple[Log | None, str]: (log_entry, status)
            Status: 'unlock', 'pending', 'no_access', 'invalid_credentials'
        """
        # Clean up expired sessions first
        self.cleanup_expired_sessions()
        
        # Parse the incoming credential
        user_id = None
        method_used = None
        nfc = None
        pin = None
        
        try:
            data = json.loads(details)
            if isinstance(data, dict):
                nfc = data.get('nfc')
                pin = data.get('pin')
            else:
                legacy_value = str(data)
                if legacy_value.startswith('NFC:'):
                    nfc = legacy_value[4:]
                elif legacy_value.startswith('PIN:'):
                    pin = legacy_value[4:]
                elif ':' in legacy_value:
                    nfc = legacy_value
                elif legacy_value.isdigit() and 4 <= len(legacy_value) <= 6:
                    pin = legacy_value
                else:
                    raise ValueError("Invalid format")
                    
        except (json.JSONDecodeError, ValueError):
            if details.startswith('NFC:'):
                nfc = details[4:]
            elif details.startswith('PIN:'):
                pin = details[4:]
            elif ':' in details:
                nfc = details
            elif details.isdigit() and 4 <= len(details) <= 6:
                pin = details
        
        # Validate the provided credential(s)
        current_method = None
        if nfc:
            nfc_card = self.nfc_repo.get_by_uid(nfc)
            if nfc_card and nfc_card.user_id:
                user_id = nfc_card.user_id
                current_method = "NFC"
                method_used = f"NFC: {nfc}"
        
        if not user_id and pin:
            pin_record = self.pin_repo.get_by_pin_code(pin)
            if pin_record and pin_record.user_id:
                user_id = pin_record.user_id
                current_method = "PIN"
                method_used = f"PIN: {pin}"
        
        # If both credentials provided, validate both belong to same user
        if nfc and pin:
            nfc_card = self.nfc_repo.get_by_uid(nfc)
            pin_record = self.pin_repo.get_by_pin_code(pin)
            
            nfc_user = nfc_card.user_id if nfc_card else None
            pin_user = pin_record.user_id if pin_record else None
            
            if not nfc_user or not pin_user:
                # One or both invalid
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.failed_attempt,
                    details=f"Invalid dual credentials: NFC={nfc_user is not None}, PIN={pin_user is not None}",
                    timestamp=datetime.utcnow()
                ), 'invalid_credentials'
            
            if nfc_user != pin_user:
                # Credentials belong to different users
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.tamper,
                    details=f"Mismatched dual credentials: NFC user {nfc_user} != PIN user {pin_user}",
                    timestamp=datetime.utcnow()
                ), 'no_access'
            
            # Both valid for same user - this is dual auth
            user_id = nfc_user
            method_used = f"DUAL: NFC:{nfc} + PIN:{pin}"
        
        if not user_id:
            return None, 'invalid_credentials'
        
        # Check vault access permissions
        users_for_vault = self.user_vault_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        
        if user_id not in vault_user_ids:
            return self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=f"No vault access: {method_used}",
                timestamp=datetime.utcnow()
            ), 'no_access'
        
        # Determine authentication mode for this vault/user
        # You can make this configurable per vault or user
        requires_dual_auth = self.vault_requires_dual_auth(vault_id)
        
        if requires_dual_auth:
            # Dual authentication required
            if nfc and pin:
                # Both factors provided - grant access
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,
                    details=method_used,
                    timestamp=datetime.utcnow()
                ), 'unlock'
            else:
                # Only one factor provided - store session and request second
                session_key = self.get_session_key(vault_id, user_id)
                LogService.auth_sessions[session_key] = {
                    'user_id': user_id,
                    'vault_id': vault_id,
                    'first_method': current_method,
                    'first_credential': nfc if nfc else pin,
                    'timestamp': time.time()
                }
                
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,  # Log as unlock attempt
                    details=f"First factor: {method_used}",
                    timestamp=datetime.utcnow()
                ), 'pending'
        else:
            # Single authentication mode - first valid credential grants access
            return self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.unlock,
                details=method_used,
                timestamp=datetime.utcnow()
            ), 'unlock'
    def extract_user_id_from_details(self, details: str) -> Optional[int]:
        """
        Extract user_id from credential details without full validation
        Used to check for existing MFA sessions
        """
        try:
            # Parse the incoming credential (similar to validate_progressive_access)
            nfc = None
            pin = None
            
            try:
                data = json.loads(details)
                if isinstance(data, dict):
                    nfc = data.get('nfc')
                    pin = data.get('pin')
                else:
                    legacy_value = str(data)
                    if legacy_value.startswith('NFC:'):
                        nfc = legacy_value[4:]
                    elif legacy_value.startswith('PIN:'):
                        pin = legacy_value[4:]
                    elif ':' in legacy_value:
                        nfc = legacy_value
                    elif legacy_value.isdigit() and 4 <= len(legacy_value) <= 6:
                        pin = legacy_value
            except (json.JSONDecodeError, ValueError):
                if details.startswith('NFC:'):
                    nfc = details[4:]
                elif details.startswith('PIN:'):
                    pin = details[4:]
                elif ':' in details:
                    nfc = details
                elif details.isdigit() and 4 <= len(details) <= 6:
                    pin = details
            
            # Quick user lookup
            if nfc:
                nfc_card = self.nfc_repo.get_by_uid(nfc)
                if nfc_card and nfc_card.user_id:
                    return nfc_card.user_id
            
            if pin:
                pin_record = self.pin_repo.get_by_pin_code(pin)
                if pin_record and pin_record.user_id:
                    return pin_record.user_id
                    
            return None
        except Exception:
            return None
    def vault_requires_dual_auth(self, vault_id: int) -> bool:
        """
        Determine if a vault requires dual authentication
        This can be stored in vault configuration or user settings
        For now, return True for high-security vaults (you can customize this)
        * means all vaults that id is less than 100 will do 2 mfa (for now)
        """
        return vault_id < 100
    def handle_second_factor(self, vault_id: int, details: str) -> tuple[Log | None, str]:
        """
        Handle second factor authentication when first factor is pending
        """
        # Parse second factor
        user_id = None
        second_method = None
        
        # Similar parsing logic as before...
        if details.startswith('NFC:'):
            nfc = details[4:]
            nfc_card = self.nfc_repo.get_by_uid(nfc)
            if nfc_card:
                user_id = nfc_card.user_id
                second_method = "NFC"
        elif details.startswith('PIN:'):
            pin = details[4:]
            pin_record = self.pin_repo.get_by_pin_code(pin)
            if pin_record:
                user_id = pin_record.user_id 
                second_method = "PIN"
        
        if not user_id:
            return None, 'invalid_credentials'
        
        # Check if there's a pending session for this user/vault
        session_key = self.get_session_key(vault_id, user_id)
        
        if session_key not in LogService.auth_sessions:
            return None, 'no_pending_session'
        
        session = LogService.auth_sessions[session_key]
        
        # Validate second factor is different from first
        if session['first_method'] == second_method:
            return self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.failed_attempt,
                details=f"Same factor repeated: {second_method}",
                timestamp=datetime.utcnow()
            ), 'invalid_credentials'
        
        # Success - both factors validated
        del LogService.auth_sessions[session_key]  # Clear session
        
        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=f"DUAL: {session['first_method']}:{session['first_credential']} + {second_method}:{details}",
            timestamp=datetime.utcnow()
        ), 'unlock' 
    # --- Event Logging Methods ---
    
    def log_vault_unlock(self, vault_id: int, user_id: int, method: str = "unknown") -> Log:
        """Log a successful vault unlock with business validation"""
        details = f"Unlock method: {method}"
        return self.repo.log_vault_unlock(vault_id=vault_id, user_id=user_id, details=details)
    
    def log_failed_unlock_attempt(self, vault_id: int, user_id: Optional[int] = None,
                                 reason: str = "invalid credentials") -> Log:
        """Log a failed unlock attempt with additional context"""
        details = f"Failure reason: {reason}"
        
        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.failed_attempt,
            details=details,
            timestamp=datetime.utcnow()
        )
    
    def log_tamper_detection(self, vault_id: int, sensor_data: str = "") -> Log:
        """Log tamper detection with sensor information"""
        details = f"Tamper detected. Sensor data: {sensor_data}"
        return self.repo.log_tamper_event(vault_id=vault_id, details=details)
    
    def log_alarm_trigger(self, vault_id: int, alarm_type: str = "general") -> Log:
        """Log alarm activation"""
        details = f"Alarm type: {alarm_type}"
        return self.repo.log_alarm_event(vault_id=vault_id, details=details)

        
    def create_log(
                    self, vault_id: Optional[int], event_type: Optional[LogEventType], 
                    user_id: Optional[int] = None, details: Optional[str] = None) -> Log | None:
        """
        Create a generic log entry only if event_type and details are provided.
        """
        if not event_type or not details:
            # skip saving if either is missing  
            return None

        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=event_type,
            details=details,
            timestamp=datetime.utcnow()
        )

    def validate_access_and_create_log(self, vault_id: int, details: str) -> Log | None:
        """
        Validates user access to a vault using NFC or PIN credentials and creates an audit log entry.
        
        This method handles both modern JSON-formatted and legacy string-formatted authentication
        details. It prioritizes NFC authentication over PIN when both are provided, validates
        user access permissions, and generates appropriate audit logs for both successful
        access and tamper attempts.
        
        Args:
            vault_id (int): Unique identifier of the vault being accessed
            details (str): Authentication details in JSON format {"nfc": "uid", "pin": "code"}
                        or legacy string format ("NFC:uid", "PIN:code", etc.)
        
        Returns:
            Log | None: Created log entry for the access attempt, or None if no valid
                    authentication credentials were provided
        
        Raises:
            No exceptions are raised - all parsing errors are handled gracefully
        """
        # Initialize authentication variables
        user_id = None          # Authenticated user ID (None until successful auth)
        method_used = None      # Authentication method for audit logging
        nfc = None             # Extracted NFC card UID
        pin = None             # Extracted PIN code
        
        # Parse authentication details with multi-format support
        try:
            # Attempt to parse as JSON (modern format)
            data = json.loads(details)
            if isinstance(data, dict):
                # Standard JSON object format: {"nfc": "uid", "pin": "code"}
                nfc = data.get('nfc')
                pin = data.get('pin')
            else:
                # JSON parsed to primitive type (legacy numeric format)
                # Handle cases like unquoted numbers that become integers
                legacy_value = str(data)
                if legacy_value.startswith('NFC:'):
                    nfc = legacy_value[4:]  # Extract UID after "NFC:" prefix
                elif legacy_value.startswith('PIN:'):
                    pin = legacy_value[4:]  # Extract PIN after "PIN:" prefix
                elif ':' in legacy_value:
                    # Assume colon-separated format is NFC (legacy format)
                    nfc = legacy_value
                elif legacy_value.isdigit() and 4 <= len(legacy_value) <= 6:
                    # Numeric string of valid PIN length (4-6 digits)
                    pin = legacy_value
                else:
                    raise ValueError("Invalid legacy format")
                    
        except (json.JSONDecodeError, ValueError):
            # Fallback to legacy string parsing for non-JSON formats
            if details.startswith('NFC:'):
                nfc = details[4:]       # Remove "NFC:" prefix
            elif details.startswith('PIN:'):
                pin = details[4:]       # Remove "PIN:" prefix
            elif ':' in details:
                # Colon-separated format assumed to be NFC UID
                nfc = details
            elif details.isdigit() and 4 <= len(details) <= 6:
                # Plain numeric string of valid PIN length
                pin = details
        
        # Primary authentication: NFC card validation
        if nfc:
            # Look up NFC card by unique identifier
            nfc_card = self.nfc_repo.get_by_uid(nfc)
            if nfc_card and nfc_card.user_id:
                # Valid NFC card found with associated user
                user_id = nfc_card.user_id
                method_used = f"NFC: {nfc}"
        
        # Secondary authentication: PIN validation (only if NFC failed)
        if not user_id and pin:
            # Look up PIN record in database
            pin_record = self.pin_repo.get_by_pin_code(pin)
            if pin_record and pin_record.user_id:
                # Valid PIN found with associated user
                user_id = pin_record.user_id
                method_used = f"PIN: {pin}"
        
        # Handle case where no valid authentication was provided
        if not user_id:
            # No matching user found for the provided credentials
            return None
        
        # Authorization check: verify user has access to the specific vault
        users_for_vault = self.user_vault_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        
        if user_id not in vault_user_ids:
            # User authenticated but lacks permission for this vault
            # Log as tamper attempt for security monitoring
            return self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=method_used,
                timestamp=datetime.utcnow()
            )
        
        # Successful authentication and authorization
        # Create audit log entry for legitimate vault access
        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=method_used,
            timestamp=datetime.utcnow()
    )