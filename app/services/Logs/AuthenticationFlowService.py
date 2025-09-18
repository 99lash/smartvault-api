from typing import Optional, Tuple
from datetime import datetime
from app.services.Logs.CredentialValidatorService import CredentialValidator
from app.services.Logs.SessionManagerService import SessionManager
from app.services.Logs.VaultAccessControllerService import VaultAccessController
from app.services.Logs.SecurityPolicy import SecurityPolicy
from app.repositories.LogRepository import LogRepository
from app.models.Log import Log, LogEventType
import time

class AuthenticationFlow:
    def __init__(self, validator: CredentialValidator, session_manager: SessionManager, access_controller: VaultAccessController, security_policy: SecurityPolicy, repo: LogRepository):
        self.validator = validator
        self.session_manager = session_manager
        self.access_controller = access_controller
        self.security_policy = security_policy
        self.repo = repo

    def progressive_access(self, vault_id: int, details: str) -> Tuple[Optional[Log], str]:
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
        self.session_manager.cleanup_expired_sessions()
        
        # Parse the incoming credential from details (supports JSON or legacy string formats)
        nfc, pin = self.validator.parse_credentials(details)
        user_id = None
        method_used = None
        current_method = None  # Track the first factor method for session storage
        
        # Validate the provided credential(s) - prioritize NFC over PIN if both present
        if nfc:
            user_id, method_used = self.validator.validate_credential(nfc, is_nfc=True)
            if user_id:
                current_method = "NFC"
        
        if not user_id and pin:
            user_id, method_used = self.validator.validate_credential(pin, is_nfc=False)
            if user_id:
                current_method = "PIN"
        
        # If both credentials provided in a single request, validate they belong to the same user
        # This handles "immediate dual auth" where client sends both factors at once
        if nfc and pin:
            nfc_user, _ = self.validator.validate_credential(nfc, is_nfc=True)
            pin_user, _ = self.validator.validate_credential(pin, is_nfc=False)
            
            if not nfc_user or not pin_user:
                # One or both invalid - log as failed attempt
                log_entry = self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.failed_attempt,
                    details=f"Invalid dual credentials: NFC={nfc_user is not None}, PIN={pin_user is not None}",
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(vault_id)
                return log_entry, 'invalid_credentials'
            
            if nfc_user != pin_user:
                # Credentials belong to different users - potential tamper attempt
                log_entry = self.repo.create(
                    vault_id=vault_id,
                    user_id=None,
                    event_type=LogEventType.tamper,
                    details=f"Mismatched dual credentials: NFC user {nfc_user} != PIN user {pin_user}",
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(vault_id)
                return log_entry, 'no_access'
            
            # Both valid for same user - immediate dual auth success
            user_id = nfc_user
            method_used = f"DUAL: NFC:{nfc} + PIN:{pin}"
        
        if not user_id:
            # No valid credential provided - reject without logging (handled by caller)
            # But if this was a potential second factor (session exists), clear to reset
            if any(key.startswith(f"vault_{vault_id}_") for key in self.session_manager.auth_sessions):
                self.session_manager.clear_sessions_for_vault(vault_id)
            return None, 'invalid_credentials'
        
        # Check if this is a second factor attempt
        session_key = self.session_manager.get_session_key(vault_id, user_id)
        if session_key in self.session_manager.auth_sessions:
            session = self.session_manager.auth_sessions[session_key]
            
            if current_method == session['first_method']:
                log_entry = self.repo.create(
                    vault_id=vault_id,
                    user_id=user_id,
                    event_type=LogEventType.failed_attempt,
                    details=f"Same factor repeated: {current_method}",
                    timestamp=datetime.utcnow()
                )
                self.session_manager.clear_sessions_for_vault(vault_id)
                return log_entry, 'invalid_credentials'
            
            second_credential = nfc if current_method == "NFC" else pin
            log_entry = self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.unlock,
                details=f"DUAL: {session['first_method']}:{session['first_credential']} + {current_method}:{second_credential}",
                timestamp=datetime.utcnow()
            )
            del self.session_manager.auth_sessions[session_key]
            return log_entry, 'unlock'
        
        # No session - proceed with first factor access validation
        
        # Verify user has access to the specific vault
        if not self.access_controller.check_access(user_id, vault_id):
            # Unauthorized access attempt - log as tamper for security audit
            log_entry = self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=f"No vault access: {method_used}",
                timestamp=datetime.utcnow()
            )
            self.session_manager.clear_sessions_for_vault(vault_id)
            return log_entry, 'no_access'
        
        # Determine authentication mode based on vault configuration
        # Currently, vaults with ID < 100 require dual auth (configurable via vault settings in future)
        requires_dual_auth = self.security_policy.requires_dual_auth(vault_id)
        
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
                session_key = self.session_manager.get_session_key(vault_id, user_id)
                self.session_manager.auth_sessions[session_key] = {
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

    def second_factor(self, vault_id: int, details: str) -> Tuple[Optional[Log], str]:
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
        nfc, pin = self.validator.parse_credentials(details)
        user_id = None
        second_method = None
        method_used = None
        
        # Determine and validate the second credential type
        if nfc:
            user_id, method_used = self.validator.validate_credential(nfc, is_nfc=True)
            if user_id:
                second_method = "NFC"
        elif pin:
            user_id, method_used = self.validator.validate_credential(pin, is_nfc=False)
            if user_id:
                second_method = "PIN"
        
        if not user_id:
            # Second credential invalid - reject and clear session to reset MFA
            self.session_manager.clear_sessions_for_vault(vault_id)
            return None, 'invalid_credentials'
        
        # Skip vault access check - already performed during first factor
        
        # Retrieve pending session for this user-vault pair
        session_key = self.session_manager.get_session_key(vault_id, user_id)
        
        if session_key not in self.session_manager.auth_sessions:
            # No pending session found - treat as invalid (not a second factor attempt)
            return None, 'no_pending_session'
        
        session = self.session_manager.auth_sessions[session_key]
        
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
        del self.session_manager.auth_sessions[session_key]  # Clear completed session
        
        log_entry = self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=f"DUAL: {session['first_method']}:{session['first_credential']} + {second_method}:{details}",
            timestamp=datetime.utcnow()
        )
        return log_entry, 'unlock'