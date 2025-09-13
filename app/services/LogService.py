from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from app.repositories.LogRepository import LogRepository
from app.repositories.UserVaultRepository import UserVaultRepository
from app.repositories.NfcCardRepository import NfcCardRepository
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
from app.models.Log import Log, LogEventType

# -----------------------------
# Service layer for Log logic
# -----------------------------
# Encapsulates business logic related to logging:
# - audit trail management
# - security event monitoring
# - log analysis and reporting
class LogService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = LogRepository(db)
        self.user_vault_repo = UserVaultRepository(db)
        self.nfc_repo = NfcCardRepository(db)
        self.pin_repo = KeypadPinsRepository(db)
        
    # --- Basic CRUD Operations ---
    
    def get_log_by_id(self, log_id: int) -> Log | None:
        """Fetch a log entry by ID"""
        return self.repo.get_by_id(log_id)
    
    def get_all_logs(self) -> List[Log]:
        """Get all log entries"""
        return self.repo.get_all()
    
    def delete_log(self, log_id: int) -> Log | None:
        """Delete a log entry by ID"""
        return self.repo.delete(log_id)
    
    # --- Vault-specific Operations ---
    
    def get_vault_logs(self, vault_id: int) -> List[Log]:
        """Get all logs for a specific vault"""
        return self.repo.get_by_vault(vault_id)
    
    def get_vault_activity_summary(self, vault_id: int, hours: int = 24) -> Dict:
        """Get activity summary for a vault in the last N hours"""
        logs = self.repo.get_logs_by_date_range(
            start_date=datetime.utcnow() - timedelta(hours=hours),
            end_date=datetime.utcnow(),
            vault_id=vault_id
        )
        
        summary = {
            "total_events": len(logs),
            "unlock_count": 0,
            "failed_attempts": 0,
            "security_alerts": 0,
            "last_activity": None
        }
        
        for log in logs:
            if log.event_type == LogEventType.unlock:
                summary["unlock_count"] += 1
            elif log.event_type == LogEventType.failed_attempt:
                summary["failed_attempts"] += 1
            elif log.event_type in [LogEventType.tamper, LogEventType.alarm]:
                summary["security_alerts"] += 1
        
        if logs:
            summary["last_activity"] = logs[0].timestamp  # Most recent
        
        return summary
    
    # --- User Activity Operations ---
    
    def get_user_logs(self, user_id: int) -> List[Log]:
        """Get all logs for a specific user"""
        return self.repo.get_by_user(user_id)
    
    def get_user_activity_summary(self, user_id: int, hours: int = 24) -> Dict:
        """Get user activity summary in the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        logs = [log for log in self.repo.get_by_user(user_id) 
                if log.timestamp >= cutoff_time]
        
        vault_access = {}
        for log in logs:
            if log.vault_id not in vault_access:
                vault_access[log.vault_id] = {
                    "unlocks": 0,
                    "failed_attempts": 0
                }
            
            if log.event_type == LogEventType.unlock:
                vault_access[log.vault_id]["unlocks"] += 1
            elif log.event_type == LogEventType.failed_attempt:
                vault_access[log.vault_id]["failed_attempts"] += 1
        
        return {
            "total_activities": len(logs),
            "vaults_accessed": len(vault_access),
            "vault_breakdown": vault_access,
            "period_hours": hours
        }
    
    # --- Security Monitoring ---
    
    def check_security_alerts(self, vault_id: Optional[int] = None, hours: int = 1) -> List[Log]:
        """Get recent security events that may need attention"""
        return self.repo.get_security_events(vault_id=vault_id, hours=hours)
    
    def is_vault_under_attack(self, vault_id: int, failed_attempts_threshold: int = 5, 
                             time_window_minutes: int = 30) -> bool:
        """Check if a vault is experiencing suspicious activity"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        failed_attempts = self.repo.get_failed_attempts_by_vault(
            vault_id=vault_id, 
            hours=time_window_minutes / 60
        )
        
        recent_failures = [log for log in failed_attempts if log.timestamp >= cutoff_time]
        return len(recent_failures) >= failed_attempts_threshold
    
    def get_suspicious_activity_report(self, hours: int = 24) -> Dict:
        """Generate a report of suspicious activities across all vaults"""
        security_events = self.repo.get_security_events(hours=hours)
        event_counts = self.repo.count_events_by_type(hours=hours)
        
        # Group by vault to identify problem vaults
        vault_issues = {}
        for event in security_events:
            if event.vault_id not in vault_issues:
                vault_issues[event.vault_id] = {
                    "failed_attempts": 0,
                    "tamper_events": 0,
                    "alarms": 0,
                    "total_events": 0
                }
            
            vault_issues[event.vault_id]["total_events"] += 1
            if event.event_type == LogEventType.failed_attempt:
                vault_issues[event.vault_id]["failed_attempts"] += 1
            elif event.event_type == LogEventType.tamper:
                vault_issues[event.vault_id]["tamper_events"] += 1
            elif event.event_type == LogEventType.alarm:
                vault_issues[event.vault_id]["alarms"] += 1
        
        return {
            "report_period_hours": hours,
            "total_security_events": len(security_events),
            "event_type_breakdown": event_counts,
            "vaults_with_issues": vault_issues,
            "high_risk_vaults": [
                vault_id for vault_id, issues in vault_issues.items()
                if issues["failed_attempts"] >= 3 or issues["tamper_events"] > 0
            ]
        }
    
    # --- Event Logging Methods ---
    
    def log_vault_unlock(self, vault_id: int, user_id: int, method: str = "unknown") -> Log:
        """Log a successful vault unlock with business validation"""
        details = f"Unlock method: {method}"
        return self.repo.log_vault_unlock(vault_id=vault_id, user_id=user_id, details=details)
    
    def log_failed_unlock_attempt(self, vault_id: int, user_id: Optional[int] = None, 
                                 reason: str = "invalid credentials") -> Log:
        """Log a failed unlock attempt with additional context"""
        details = f"Failure reason: {reason}"
        
        # Business logic: Check if this triggers a security alert
        if self.is_vault_under_attack(vault_id):
            # Could trigger additional security measures here
            details += " | SECURITY ALERT: Multiple failed attempts detected"
        
        return self.repo.log_failed_attempt(vault_id=vault_id, user_id=user_id, details=details)
    
    def log_tamper_detection(self, vault_id: int, sensor_data: str = "") -> Log:
        """Log tamper detection with sensor information"""
        details = f"Tamper detected. Sensor data: {sensor_data}"
        return self.repo.log_tamper_event(vault_id=vault_id, details=details)
    
    def log_alarm_trigger(self, vault_id: int, alarm_type: str = "general") -> Log:
        """Log alarm activation"""
        details = f"Alarm type: {alarm_type}"
        return self.repo.log_alarm_event(vault_id=vault_id, details=details)
    
    # --- Reporting and Analytics ---
    
    def get_activity_report(self, start_date: datetime, end_date: datetime, 
                           vault_id: Optional[int] = None) -> Dict:
        """Generate comprehensive activity report for a date range"""
        logs = self.repo.get_logs_by_date_range(start_date, end_date, vault_id)
        
        report = {
            "period": {
                "start": start_date,
                "end": end_date,
                "vault_id": vault_id
            },
            "total_events": len(logs),
            "event_breakdown": {},
            "daily_activity": {},
            "busiest_hours": {}
        }
        
        # Count events by type
        for log in logs:
            event_type = log.event_type.value
            report["event_breakdown"][event_type] = report["event_breakdown"].get(event_type, 0) + 1
            
            # Daily breakdown
            day = log.timestamp.date()
            if day not in report["daily_activity"]:
                report["daily_activity"][day] = 0
            report["daily_activity"][day] += 1
            
            # Hourly breakdown
            hour = log.timestamp.hour
            if hour not in report["busiest_hours"]:
                report["busiest_hours"][hour] = 0
            report["busiest_hours"][hour] += 1
        
        return report
    
    def get_paginated_logs(self, page: int = 1, per_page: int = 20, 
                          vault_id: Optional[int] = None, 
                          event_type: Optional[LogEventType] = None) -> List[Log]:
        """Get paginated logs with optional filters"""
        return self.repo.get_logs_with_pagination(
            page=page, per_page=per_page, vault_id=vault_id, event_type=event_type
        )
    
    # --- Maintenance Operations ---
    
    def cleanup_old_logs(self, retention_days: int = 90) -> int:
        """Clean up logs older than specified days"""
        deleted_count = self.repo.delete_old_logs(days=retention_days)
        
        # Log the cleanup operation itself
        if deleted_count > 0:
            # This would need a system vault ID or handle system events differently
            pass  # Could log to a separate system events table
        
        return deleted_count
    
    def get_storage_stats(self) -> Dict:
        """Get statistics about log storage for maintenance planning"""
        all_logs = self.repo.get_all()
        
        if not all_logs:
            return {"total_logs": 0, "oldest_log": None, "newest_log": None}
        
        # Sort by timestamp to find oldest and newest
        sorted_logs = sorted(all_logs, key=lambda x: x.timestamp)
        
        return {
            "total_logs": len(all_logs),
            "oldest_log": sorted_logs[0].timestamp,
            "newest_log": sorted_logs[-1].timestamp,
            "storage_period_days": (sorted_logs[-1].timestamp - sorted_logs[0].timestamp).days
        }
        
    def create_log(
    self, 
    vault_id: Optional[int], 
    event_type: Optional[LogEventType], 
    user_id: Optional[int] = None, 
    details: Optional[str] = None
    ) -> Log | None:
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
    


    def validate_access_and_create_log(
        self,
        vault_id: int,
        details: str
    ) -> Log | None:
        """
        Validate access via NFC UID or keypad PIN and create log if valid.
        Only creates log if a matching user with vault access is found.
        Uses LogEventType.unlock for successful validation.
        """
        user_id = None
        
        # Determine input type
        if ':' in details:
            # Treat as NFC UID
            nfc_card = self.nfc_repo.get_by_uid(details)
            if nfc_card and nfc_card.user_id:
                user_id = nfc_card.user_id
        elif details.isdigit() and 4 <= len(details) <= 6:
            # Treat as keypad PIN (4-6 digits)
            pin_record = self.pin_repo.get_by_pin_code(details)
            if pin_record and pin_record.user_id:
                user_id = pin_record.user_id
        
        if not user_id:
            # No matching user found for the provided details
            return None
        
        # Check if user has access to the vault
        users_for_vault = self.user_vault_repo.get_users_for_vault(vault_id)
        vault_user_ids = [user.id for user in users_for_vault]
        
        if user_id not in vault_user_ids:
            # User does not have access to this vault - log as tamper
            return self.repo.create(
                vault_id=vault_id,
                user_id=user_id,
                event_type=LogEventType.tamper,
                details=details,
                timestamp=datetime.utcnow()
            )
        
        # Valid access: create the log as unlock
        return self.repo.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=details,
            timestamp=datetime.utcnow()
        )
