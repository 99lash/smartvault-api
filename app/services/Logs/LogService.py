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
        self.vault_repo = None  # Will be initialized when needed for device_id lookup
        self.validator = CredentialValidator(self.nfc_repo, self.pin_repo)
        self.session_manager = SessionManager()
        self.access_controller = VaultAccessController(self.user_vault_repo)
        self.security_policy = SecurityPolicy()
        self.auth_flow = AuthenticationFlow(self.validator, self.session_manager, self.access_controller, self.security_policy, self.repo)

    def _get_vault_id_by_device_id(self, device_id: str) -> int | None:
        """
        Look up vault ID by device_id string.

        Args:
            device_id (str): The ESP32 device identifier

        Returns:
            int | None: Vault ID if found, None otherwise
        """
        if self.vault_repo is None:
            from app.repositories.VaultRepository import VaultRepository
            self.vault_repo = VaultRepository(self.repo.db)

        vault = self.vault_repo.get_by_device_id(device_id)
        return vault.id if vault else None

    def get_all_logs(self) -> List[Log]:
        """Get all log entries"""
        return self.repo.get_all()
    
    def delete_log(self, log_id: int) -> Log | None:
        """Delete a log entry by ID"""
        return self.repo.delete(log_id)

    def bulk_delete_logs(self, device_id: str | None = None, user_id: int | None = None,
                         event_type: str | None = None, older_than_days: int | None = None,
                         delete_all: bool = False) -> int:
        """
        Bulk delete logs based on various criteria.

        Args:
            device_id (Optional[str]): Delete logs for specific ESP32 device
            user_id (Optional[int]): Delete logs for specific user
            event_type (Optional[str]): Delete logs of specific event type
            older_than_days (Optional[int]): Delete logs older than X days
            delete_all (bool): If True, ignore other filters and delete all logs

        Returns:
            int: Number of logs deleted
        """
        from datetime import datetime, timedelta

        # Build filter conditions
        filters = []

        if not delete_all:
            if device_id is not None:
                vault_id = self._get_vault_id_by_device_id(device_id)
                if vault_id is not None:
                    filters.append(self.repo.model.vault_id == vault_id)
            if user_id is not None:
                filters.append(self.repo.model.user_id == user_id)
            if event_type is not None:
                # Convert string to enum if needed
                try:
                    event_enum = LogEventType(event_type)
                    filters.append(self.repo.model.event_type == event_enum)
                except ValueError:
                    # If not a valid enum, try as string match in details
                    filters.append(self.repo.model.details.contains(event_type))
            if older_than_days is not None:
                cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
                filters.append(self.repo.model.created_at < cutoff_date)

        # Execute bulk delete
        deleted_count = self.repo.bulk_delete(filters)
        return deleted_count

    def clear_sessions_for_vault(self, device_id: str):
        """
        Clear authentication sessions for a specific vault to reset MFA state.

        Args:
            device_id (str): The ESP32 device identifier.
        """
        # For sessions, we still use device_id since that's what the ESP32 sends
        self.session_manager.clear_sessions_for_vault(device_id)

    def validate_progressive_access(self, device_id: str, details: str) -> tuple[Log | None, str]:
        # For authentication flow, we still use device_id since that's what ESP32 sends
        return self.auth_flow.progressive_access(device_id, details)

    def handle_second_factor(self, device_id: str, details: str) -> tuple[Log | None, str]:
        # For authentication flow, we still use device_id since that's what ESP32 sends
        return self.auth_flow.second_factor(device_id, details)
    
    # --- Event Logging Methods ---
    # -----------------------------
    # These methods provide high-level logging for specific events.
    # Note: Some repo methods (e.g., log_vault_unlock) may need implementation if not present.
    
    def log_vault_unlock(self, device_id: str, user_id: int, method: str = "unknown") -> Log:
        """
        Log a successful vault unlock event with contextual details.

        This is a convenience wrapper; in production, integrate with audit trails.

        Args:
            device_id (str): The ESP32 device identifier.
            user_id (int): The user who unlocked it.
            method (str): The unlock method (e.g., "NFC", "PIN").

        Returns:
            Log: The created log entry.
        """
        details = f"Unlock method: {method}"
        vault_id = self._get_vault_id_by_device_id(device_id)
        if vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")
        return self.repo.log_vault_unlock(vault_id=vault_id, user_id=user_id, details=details)
    
    def log_failed_unlock_attempt(self, device_id: str, user_id: Optional[int] = None,
                                   reason: str = "invalid credentials") -> Log:
        """
        Log a failed unlock attempt, including failure reason for security analysis.

        Args:
            device_id (str): The ESP32 device identifier.
            user_id (Optional[int]): The user ID if known, None for anonymous.
            reason (str): Reason for failure (e.g., "invalid PIN").

        Returns:
            Log: The created failed attempt log entry.
        """
        details = f"Failure reason: {reason}"

        vault_id = self._get_vault_id_by_device_id(device_id)
        if vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")

        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.failed_attempt,
            details=details,
            timestamp=datetime.utcnow()
        )
    
    def log_tamper_detection(self, device_id: str, sensor_data: str = "") -> Log:
        """
        Log a tamper detection event, often from physical sensors or unauthorized access.

        Args:
            device_id (str): The ESP32 device identifier.
            sensor_data (str): Optional sensor readings or details.

        Returns:
            Log: The tamper log entry.
        """
        details = f"Tamper detected. Sensor data: {sensor_data}"
        vault_id = self._get_vault_id_by_device_id(device_id)
        if vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")
        return self.repo.log_tamper_event(vault_id=vault_id, details=details)
    
    def log_alarm_trigger(self, device_id: str, alarm_type: str = "general") -> Log:
        """
        Log an alarm trigger event for security notifications.

        Args:
            device_id (str): The ESP32 device identifier.
            alarm_type (str): Type of alarm (e.g., "motion", "breach").

        Returns:
            Log: The alarm log entry.
        """
        details = f"Alarm type: {alarm_type}"
        vault_id = self._get_vault_id_by_device_id(device_id)
        if vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")
        return self.repo.log_alarm_event(vault_id=vault_id, details=details)

        
    def create_log(
                     self, device_id: Optional[str], event_type: Optional[LogEventType],
                     user_id: Optional[int] = None, details: Optional[str] = None) -> Log | None:
        """
        Create a generic log entry for arbitrary events.

        Skips creation if event_type or details are missing to avoid incomplete logs.

        Args:
            device_id (Optional[str]): Associated ESP32 device identifier.
            event_type (Optional[LogEventType]): The event type.
            user_id (Optional[int]): Associated user ID (None if unknown).
            details (Optional[str]): Event details.

        Returns:
            Log | None: Created log or None if invalid inputs.
        """
        if not event_type or not details:
            # Skip logging incomplete events
            return None

        vault_id = self._get_vault_id_by_device_id(device_id) if device_id else None
        if device_id and vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")

        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=event_type,
            details=details,
            timestamp=datetime.utcnow()
        )

    def validate_access_and_create_log(self, device_id: str, details: str) -> Log | None:
        """
        Legacy method for single-factor validation and logging (pre-MFA).

        Validates access using NFC or PIN (prioritizes NFC), checks permissions, and logs the outcome.
        Handles parsing errors gracefully. Use validate_progressive_access for MFA support.

        Args:
            device_id (str): ESP32 device identifier of the vault being accessed.
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
        vault_id = self._get_vault_id_by_device_id(device_id)
        if vault_id is None:
            raise ValueError(f"Vault with device_id '{device_id}' not found")

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