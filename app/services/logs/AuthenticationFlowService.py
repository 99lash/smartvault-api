from typing import Optional, Tuple
from datetime import datetime
from app.services.logs.CredentialValidatorService import CredentialValidator
from app.services.logs.SessionManagerService import SessionManager
from app.services.logs.VaultAccessControllerService import VaultAccessController
from app.services.logs.SecurityPolicy import SecurityPolicy
from app.repositories.LogRepository import LogRepository
from app.repositories.VaultRepository import VaultRepository
from app.models.Log import Log, LogEventType
import time

class AuthenticationFlow:
    def __init__(self, validator: CredentialValidator, session_manager: SessionManager, access_controller: VaultAccessController, security_policy: SecurityPolicy, repo: LogRepository, vault_repo: VaultRepository):
        self.validator = validator
        self.session_manager = session_manager
        self.access_controller = access_controller
        self.security_policy = security_policy
        self.repo = repo
        self.vault_repo = vault_repo

    def progressive_access(self, device_id: str, details: str) -> Tuple[Optional[Log], str]:
        # Clean up expired sessions first to ensure fresh state
        self.session_manager.cleanup_expired_sessions()

        # Look up vault_id from device_id
        vault = self.vault_repo.get_by_device_id(device_id)
        if not vault:
            # Handle case where device_id doesn't exist in vaults table
            return None, 'invalid_device'
        vault_id = vault.id

        # Parse the incoming credential from details (supports JSON or legacy string formats)
        nfc, pin = self.validator.parse_credentials(details)
        user_id = None
        method_used = None
        current_method = None  # Track the first factor method for session storage
        
        # Validate the provided credential(s) using vault-centric approach
        if nfc:
            user_id, method_used = self.validator.validate_credential_for_vault(nfc, is_nfc=True, device_id=device_id, access_controller=self.access_controller)
            if user_id:
                current_method = "NFC"

        if not user_id and pin:
            user_id, method_used = self.validator.validate_credential_for_vault(pin, is_nfc=False, device_id=device_id, access_controller=self.access_controller)
            if user_id:
                current_method = "PIN"
        
        # If both credentials provided in a single request, validate they both work for this vault
        # This handles "immediate dual auth" where client sends both factors at once
        if nfc and pin:
            nfc_user, _ = self.validator.validate_credential_for_vault(nfc, is_nfc=True, device_id=device_id, access_controller=self.access_controller)
            pin_user, _ = self.validator.validate_credential_for_vault(pin, is_nfc=False, device_id=device_id, access_controller=self.access_controller)

            if not nfc_user or not pin_user:
                # One or both invalid for this vault - log as failed attempt
                log_entry = self.repo.create(
                    device_id=device_id,
                    user_id=None,
                    event_type=LogEventType.failed_attempt,
                    details=f"Invalid dual credentials for vault: NFC={nfc_user is not None}, PIN={pin_user is not None}",
                    vault_id=vault_id,
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(device_id)
                return log_entry, 'invalid_credentials'

            if nfc_user != pin_user:
                # Credentials belong to different users - in vault-centric approach, this might be OK
                # if both users have vault access, but for now we'll keep the strict checking
                log_entry = self.repo.create(
                    device_id=device_id,
                    user_id=None,
                    event_type=LogEventType.tamper,
                    details=f"Mismatched dual credentials: NFC user {nfc_user} != PIN user {pin_user}",
                    vault_id=vault_id,
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(device_id)
                return log_entry, 'no_access'

            # Both valid for same user - immediate dual auth success
            user_id = nfc_user
            method_used = f"DUAL: NFC:{nfc} + PIN:{pin}"
        
        if not user_id:
            # No valid credential provided - reject without logging (handled by caller)
            # But if this was a potential second factor (session exists), clear to reset
            if any(key.startswith(f"vault_{device_id}_") for key in self.session_manager.auth_sessions):
                self.session_manager.clear_sessions_for_vault(device_id)
            return None, 'invalid_credentials'
        
        # Check if this is a second factor attempt
        session_key = self.session_manager.get_session_key(device_id, user_id)
        if session_key in self.session_manager.auth_sessions:
            session = self.session_manager.auth_sessions[session_key]
            
            if current_method == session['first_method']:
                log_entry = self.repo.create(
                    device_id=device_id,
                    user_id=user_id,
                    event_type=LogEventType.failed_attempt,
                    details=f"Same factor repeated: {current_method}",
                    vault_id=vault_id,
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(device_id)
                return log_entry, 'invalid_credentials'
            
            second_credential = nfc if current_method == "NFC" else pin
            log_entry = self.repo.create(
                device_id=device_id,
                user_id=user_id,
                event_type=LogEventType.unlock,
                details=f"DUAL: {session['first_method']}:{session['first_credential']} + {current_method}:{second_credential}",
                vault_id=vault_id,
                timestamp=datetime.utcnow()
            )
            del self.session_manager.auth_sessions[session_key]
            return log_entry, 'unlock'
        
        # No session - proceed with first factor access validation
        
        # Verify user has access to the specific vault
        if not self.access_controller.check_access(user_id, device_id):
            # Unauthorized access attempt - log as tamper for security audit
            log_entry = self.repo.create(
                device_id=device_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=f"No vault access: {method_used}",
                vault_id=vault_id,
                timestamp=datetime.utcnow()
            )
            self.session_manager.clear_sessions_for_vault(device_id)
            return log_entry, 'no_access'
        
        # Determine authentication mode based on vault configuration
        # Currently, vaults with ID < 100 require dual auth (configurable via vault settings in future)
        requires_dual_auth = self.security_policy.requires_dual_auth(device_id)
        
        if requires_dual_auth:
            # Dual authentication required for this vault
            if nfc and pin: 
                # Both factors provided in single request - grant immediate access
                log_entry = self.repo.create(
                    device_id=device_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,
                    details=method_used,
                    vault_id=vault_id,
                    timestamp=datetime.utcnow()
                )
                return log_entry, 'unlock'
            else:
                # Only one factor provided - initiate MFA by storing session state
                session_key = self.session_manager.get_session_key(device_id, user_id)
                self.session_manager.auth_sessions[session_key] = {
                    'user_id': user_id,
                    'device_id': device_id,
                    'first_method': current_method,
                    'first_credential': nfc if nfc else pin,
                    'timestamp': time.time()
                }
                
                # Log the first factor attempt as pending unlock
                log_entry = self.repo.create(
                    device_id=device_id,
                    user_id=user_id,
                    event_type=LogEventType.unlock,  # Log as unlock attempt (pending)
                    details=f"First factor: {method_used}",
                    vault_id=vault_id,
                    timestamp=datetime.utcnow()
                )
                return log_entry, 'pending'
        else:
            # Single authentication mode - grant access with single valid credential
            log_entry = self.repo.create(
                device_id=device_id,
                user_id=user_id,
                event_type=LogEventType.unlock,
                details=method_used,
                vault_id=vault_id,
                timestamp=datetime.utcnow()
            )
            return log_entry, 'unlock'

    def second_factor(self, device_id: str, details: str) -> Tuple[Optional[Log], str]:
        # Look up vault_id from device_id
        vault = self.vault_repo.get_by_device_id(device_id)
        if not vault:
            # Handle case where device_id doesn't exist in vaults table
            return None, 'invalid_device'
        vault_id = vault.id

        # Parse and validate the second factor credential
        nfc, pin = self.validator.parse_credentials(details)
        user_id = None
        second_method = None
        method_used = None
        
        # Determine and validate the second credential type using vault-centric approach
        if nfc:
            user_id, method_used = self.validator.validate_credential_for_vault(nfc, is_nfc=True, device_id=device_id, access_controller=self.access_controller)
            if user_id:
                second_method = "NFC"
        elif pin:
            user_id, method_used = self.validator.validate_credential_for_vault(pin, is_nfc=False, device_id=device_id, access_controller=self.access_controller)
            if user_id:
                second_method = "PIN"
        
        if not user_id:
            # Second credential invalid - reject and clear session to reset MFA
            self.session_manager.clear_sessions_for_vault(device_id)
            return None, 'invalid_credentials'
        
        # Skip vault access check - already performed during first factor
        
        # Retrieve pending session for this user-vault pair
        session_key = self.session_manager.get_session_key(device_id, user_id)

        if session_key not in self.session_manager.auth_sessions:
            # No pending session found for this user-vault pair
            return None, 'no_pending_session'
        
        session = self.session_manager.auth_sessions[session_key]
        
        # Ensure second factor is different from first to prevent replay attacks
        if session['first_method'] == second_method:
            log_entry = self.repo.create(
                device_id=device_id,
                user_id=user_id,
                event_type=LogEventType.failed_attempt,
                details=f"Same factor repeated: {second_method}",
                vault_id=vault_id,
                timestamp=datetime.utcnow()
            )
            return log_entry, 'invalid_credentials'
        
        # Dual authentication successful - clear session and log unlock
        del self.session_manager.auth_sessions[session_key]  # Clear completed session
        log_entry = self.repo.create(
            device_id=device_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=f"DUAL: {session['first_method']}:{session['first_credential']} + {second_method}:{details}",
            vault_id=vault_id,
            timestamp=datetime.utcnow()
        )
        return log_entry, 'unlock'