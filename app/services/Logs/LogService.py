from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from app.repositories.LogRepository import LogRepository
from app.repositories.UserVaultRepository import UserVaultRepository
from app.repositories.NfcCardRepository import NfcCardRepository
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
from app.models.Log import Log, LogEventType
from app.services.Logs.SecurityPolicy import SecurityPolicy
from app.services.Logs.CredentialValidatorService import CredentialValidator
from app.services.Logs.SessionManagerService import SessionManager
from app.services.Logs.VaultAccessControllerService import VaultAccessController
from app.services.Logs.AuthenticationFlowService import AuthenticationFlow
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
# It uses in-memory sessions for MFA state (TODO: for smartvault version 2 might use Redis).

class LogService:

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
        self.validator = CredentialValidator(self.nfc_repo, self.pin_repo)
        self.session_manager = SessionManager()
        self.access_controller = VaultAccessController(self.user_vault_repo)
        self.security_policy = SecurityPolicy()
        self.auth_flow = AuthenticationFlow(self.validator, self.session_manager, self.access_controller, self.security_policy, self.repo)

    def get_all_logs(self) -> List[Log]:
        """Get all log entries"""
        return self.repo.get_all()
    
    def delete_log(self, log_id: int) -> Log | None:
        """Delete a log entry by ID"""
        return self.repo.delete(log_id)

    def clear_sessions_for_vault(self, vault_id: int):
        """
        Clear authentication sessions for a specific vault to reset MFA state.
        
        Args:
            vault_id (int): The vault ID.
        """
        self.session_manager.clear_sessions_for_vault(vault_id)

    def validate_progressive_access(self, vault_id: int, details: str) -> tuple[Log | None, str]:
        return self.auth_flow.progressive_access(vault_id, details)

    def handle_second_factor(self, vault_id: int, details: str) -> tuple[Log | None, str]:
        return self.auth_flow.second_factor(vault_id, details)
    
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
        nfc, pin = self.validator.parse_credentials(details)
        
        # Primary authentication: NFC card validation (prioritized over PIN)
        if nfc:
            user_id, method_used = self.validator.validate_credential(nfc, True)
        
        # Secondary authentication: PIN validation (fallback if NFC failed)
        if not user_id and pin:
            user_id, method_used = self.validator.validate_credential(pin, False)
        
        # Handle case where no valid authentication was provided
        if not user_id:
            # No matching user found for the provided credentials - silent failure
            return None
        
        # Authorization check: verify user has access to the specific vault
        if not self.access_controller.check_access(user_id, vault_id):
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