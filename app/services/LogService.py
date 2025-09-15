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
#
# This class manages authentication sessions and progressive access validation for vault unlocks.
# It uses in-memory sessions for MFA state (consider Redis for production scalability).
class LogService:
    auth_sessions: Dict[str, Dict] = {}

    def __init__(self, db: Session):
        """
        Initialize the LogService with database repositories.
        
        Args:
            db (Session): SQLAlchemy database session.
        """
        # Initialize repository with a database session
        self.repo = LogRepository(db)
        self.user_vault_repo = UserVaultRepository(db)
        self.nfc_repo = NfcCardRepository(db)
        self.pin_repo = KeypadPinsRepository(db)
    # -------------------------------
    # Multi-Factor Authentication (MFA) Helpers
    # -------------------------------
    # These methods manage session state and key generation for progressive authentication.
    def get_session_key(self, vault_id: int, user_id: int) -> str:
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
        # Clean up expired sessions first to ensure fresh state
        self.cleanup_expired_sessions()
        
        # Parse the incoming credential from details (supports JSON or legacy string formats)
        nfc, pin = self._parse_credentials(details)
        user_id = None
        method_used = None
        current_method = None  # Track the first factor method for session storage
        
        # Validate the provided credential(s) - prioritize NFC over PIN if both present
        if nfc:
            user_id, method_used = self._validate_credential(nfc, is_nfc=True)
            if user_id:
                current_method = "NFC"
        
        if not user_id and pin:
            user_id, method_used = self._validate_credential(pin, is_nfc=False)
            if user_id:
                current_method = "PIN"
        
        # If both credentials provided in a single request, validate they belong to the same user
        # This handles "immediate dual auth" where client sends both factors at once
        if nfc and pin:
            nfc_user, _ = self._validate_credential(nfc, is_nfc=True)
            pin_user, _ = self._validate_credential(pin, is_nfc=False)
            
            if not nfc_user or not pin_user:
                # One or both invalid - log as failed attempt
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.failed_attempt,
                    details=f"Invalid dual credentials: NFC={nfc_user is not None}, PIN={pin_user is not None}",
                    timestamp=datetime.utcnow()
                ), 'invalid_credentials'
            
            if nfc_user != pin_user:
                # Credentials belong to different users - potential tamper attempt
                return self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.tamper,
                    details=f"Mismatched dual credentials: NFC user {nfc_user} != PIN user {pin_user}",
                    timestamp=datetime.utcnow()
                ), 'no_access'
            
            # Both valid for same user - immediate dual auth success
            user_id = nfc_user
            method_used = f"DUAL: NFC:{nfc} + PIN:{pin}"
        
        if not user_id:
            # No valid credential provided - reject without logging (handled by caller)
            return None, 'invalid_credentials'
        
        # Verify user has access to the specific vault
        if not self._check_vault_access(user_id, vault_id, method_used):
            return None, 'no_access'
        
        # Determine authentication mode based on vault configuration
        # Currently, vaults with ID < 100 require dual auth (configurable via vault settings in future)
        requires_dual_auth = self.vault_requires_dual_auth(vault_id)
        
        if requires_dual_auth:
            # Dual authentication required for this vault
            if nfc and pin:
                # Both factors provided in single request - grant immediate access
                log_entry = self.repo.create(
                    vault_id=vault_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,
                    details=method_used,
                    timestamp=datetime.utcnow()
                )
                return log_entry, 'unlock'
            else:
                # Only one factor provided - initiate MFA by storing session state
                session_key = self.get_session_key(vault_id, user_id)
                LogService.auth_sessions[session_key] = {
                    'user_id': user_id,
                    'vault_id': vault_id,
                    'first_method': current_method,
                    'first_credential': nfc if nfc else pin,
                    'timestamp': time.time()
                }
                
                # Log the first factor attempt as pending unlock
                log_entry = self.repo.create(
                    vault_id=vault_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,  # Log as unlock attempt (pending)
                    details=f"First factor: {method_used}",
                    timestamp=datetime.utcnow()
                )
                return log_entry, 'pending'
        else:
            # Single authentication mode - grant access with single valid credential
            log_entry = self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.unlock,
                details=method_used,
                timestamp=datetime.utcnow()
            )
            return log_entry, 'unlock'
    def _parse_credentials(self, details: str) -> tuple[Optional[str], Optional[str]]:
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
            nfc, pin = self._parse_credentials(details)
            
            # Quick user lookup - prioritize NFC, then PIN
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
            # Swallow exceptions to ensure quick failure for session check
            return None
    def vault_requires_dual_auth(self, vault_id: int) -> bool:
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
    def handle_second_factor(self, vault_id: int, details: str) -> tuple[Log | None, str]:
        """
        Handle second factor authentication when first factor is pending in session.
        
        Validates the second credential, ensures it's different from the first, and completes
        the dual auth if successful. Vault access is skipped (already validated in first factor).
        
        Args:
            vault_id (int): The ID of the vault.
            details (str): Second factor details (NFC or PIN).
            
        Returns:
            tuple[Log | None, str]: (log_entry, status) - Status: 'unlock' or 'invalid_credentials'.
        """
        # Parse and validate the second factor credential
        nfc, pin = self._parse_credentials(details)
        user_id = None
        second_method = None
        method_used = None
        
        # Determine and validate the second credential type
        if nfc:
            user_id, method_used = self._validate_credential(nfc, is_nfc=True)
            if user_id:
                second_method = "NFC"
        elif pin:
            user_id, method_used = self._validate_credential(pin, is_nfc=False)
            if user_id:
                second_method = "PIN"
        
        if not user_id:
            # Second credential invalid - reject without session check
            return None, 'invalid_credentials'
        
        # Skip vault access check - already performed during first factor
        
        # Retrieve pending session for this user-vault pair
        session_key = self.get_session_key(vault_id, user_id)
        
        if session_key not in LogService.auth_sessions:
            # No pending session found - treat as invalid (not a second factor attempt)
            return None, 'no_pending_session'
        
        session = LogService.auth_sessions[session_key]
        
        # Ensure second factor is different from first to prevent replay attacks
        if session['first_method'] == second_method:
            log_entry = self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.failed_attempt,
                details=f"Same factor repeated: {second_method}",
                timestamp=datetime.utcnow()
            )
            return log_entry, 'invalid_credentials'
        
        # Dual authentication successful - clear session and log unlock
        del LogService.auth_sessions[session_key]  # Clear completed session
        
        log_entry = self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=f"DUAL: {session['first_method']}:{session['first_credential']} + {second_method}:{details}",
            timestamp=datetime.utcnow()
        )
        return log_entry, 'unlock'
    
    def _validate_credential(self, credential: str, is_nfc: bool) -> tuple[Optional[int], Optional[str]]:
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

    def _check_vault_access(self, user_id: int, vault_id: int, method_used: str) -> bool:
        """
        Check if the authenticated user has access to the specified vault.
        
        Queries user-vault associations; logs a tamper event if unauthorized.
        
        Args:
            user_id (int): The ID of the authenticating user.
            vault_id (int): The ID of the vault.
            method_used (str): The authentication method for logging.
            
        Returns:
            bool: True if access granted, False if denied (tamper logged).
        """
        # Retrieve users authorized for this vault
        users_for_vault = self.user_vault_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        
        if user_id not in vault_user_ids:
            # Unauthorized access attempt - log as tamper for security audit
            self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=f"No vault access: {method_used}",
                timestamp=datetime.utcnow()
            )
            return False
        return True
    # --- Event Logging Methods ---
    # -----------------------------
    # These methods provide high-level logging for specific events.
    # Note: Some repo methods (e.g., log_vault_unlock) may need implementation if not present.
    
    def log_vault_unlock(self, vault_id: int, user_id: int, method: str = "unknown") -> Log:
        """
        Log a successful vault unlock event with contextual details.
        
        This is a convenience wrapper; in production, integrate with audit trails.
        
        Args:
            vault_id (int): The unlocked vault ID.
            user_id (int): The user who unlocked it.
            method (str): The unlock method (e.g., "NFC", "PIN").
            
        Returns:
            Log: The created log entry.
        """
        details = f"Unlock method: {method}"
        return self.repo.log_vault_unlock(vault_id=vault_id, user_id=user_id, details=details)
    
    def log_failed_unlock_attempt(self, vault_id: int, user_id: Optional[int] = None,
                                 reason: str = "invalid credentials") -> Log:
        """
        Log a failed unlock attempt, including failure reason for security analysis.
        
        Args:
            vault_id (int): The targeted vault ID.
            user_id (Optional[int]): The user ID if known, None for anonymous.
            reason (str): Reason for failure (e.g., "invalid PIN").
            
        Returns:
            Log: The created failed attempt log entry.
        """
        details = f"Failure reason: {reason}"
        
        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.failed_attempt,
            details=details,
            timestamp=datetime.utcnow()
        )
    
    def log_tamper_detection(self, vault_id: int, sensor_data: str = "") -> Log:
        """
        Log a tamper detection event, often from physical sensors or unauthorized access.
        
        Args:
            vault_id (int): The affected vault ID.
            sensor_data (str): Optional sensor readings or details.
            
        Returns:
            Log: The tamper log entry.
        """
        details = f"Tamper detected. Sensor data: {sensor_data}"
        return self.repo.log_tamper_event(vault_id=vault_id, details=details)
    
    def log_alarm_trigger(self, vault_id: int, alarm_type: str = "general") -> Log:
        """
        Log an alarm trigger event for security notifications.
        
        Args:
            vault_id (int): The vault triggering the alarm.
            alarm_type (str): Type of alarm (e.g., "motion", "breach").
            
        Returns:
            Log: The alarm log entry.
        """
        details = f"Alarm type: {alarm_type}"
        return self.repo.log_alarm_event(vault_id=vault_id, details=details)

        
    def create_log(
                    self, vault_id: Optional[int], event_type: Optional[LogEventType],
                    user_id: Optional[int] = None, details: Optional[str] = None) -> Log | None:
        """
        Create a generic log entry for arbitrary events.
        
        Skips creation if event_type or details are missing to avoid incomplete logs.
        
        Args:
            vault_id (Optional[int]): Associated vault ID.
            event_type (Optional[LogEventType]): The event type.
            user_id (Optional[int]): Associated user ID (None if unknown).
            details (Optional[str]): Event details.
            
        Returns:
            Log | None: Created log or None if invalid inputs.
        """
        if not event_type or not details:
            # Skip logging incomplete events
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
        Legacy method for single-factor validation and logging (pre-MFA).
        
        Validates access using NFC or PIN (prioritizes NFC), checks permissions, and logs the outcome.
        Handles parsing errors gracefully. Use validate_progressive_access for MFA support.
        
        Args:
            vault_id (int): Unique identifier of the vault being accessed.
            details (str): Authentication details in JSON or legacy string format.
        
        Returns:
            Log | None: Created log entry (unlock or tamper), or None if invalid credentials.
        
        Raises:
            No exceptions - parsing/validation errors return None or tamper log.
        """
        # Initialize authentication variables
        user_id = None          # Authenticated user ID (None until successful auth)
        method_used = None      # Authentication method for audit logging
        nfc = None             # Extracted NFC card UID
        pin = None             # Extracted PIN code
        
        # Parse authentication details with multi-format support (JSON or string)
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
        
        # Primary authentication: NFC card validation (prioritized over PIN)
        if nfc:
            # Look up NFC card by unique identifier in database
            nfc_card = self.nfc_repo.get_by_uid(nfc)
            if nfc_card and nfc_card.user_id:
                # Valid NFC card found with associated user
                user_id = nfc_card.user_id
                method_used = f"NFC: {nfc}"
        
        # Secondary authentication: PIN validation (fallback if NFC failed)
        if not user_id and pin:
            # Look up PIN record in database
            pin_record = self.pin_repo.get_by_pin_code(pin)
            if pin_record and pin_record.user_id:
                # Valid PIN found with associated user
                user_id = pin_record.user_id
                method_used = f"PIN: {pin}"
        
        # Handle case where no valid authentication was provided
        if not user_id:
            # No matching user found for the provided credentials - silent failure
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