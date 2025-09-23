from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List, Optional
from .Repository import Repository
from app.models.Log import Log, LogEventType


class LogRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, Log)

    def get_by_vault(self, vault_id: int) -> List[Log]:
        """Get all logs for a specific vault"""
        return self.db.query(self.model).filter(self.model.vault_id == vault_id).all()

    def get_by_user(self, user_id: int) -> List[Log]:
        """Get all logs for a specific user"""
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()

    def get_by_event_type(self, event_type: LogEventType) -> List[Log]:
        """Get all logs of a specific event type"""
        return self.db.query(self.model).filter(self.model.event_type == event_type).all()

    def get_by_vault_and_event_type(self, vault_id: int, event_type: LogEventType) -> List[Log]:
        """Get logs for a specific vault and event type"""
        return (
            self.db.query(self.model)
            .filter(self.model.vault_id == vault_id, self.model.event_type == event_type)
            .all()
        )

    def get_recent_logs(self, hours: int = 24) -> List[Log]:
        """Get logs from the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(self.model)
            .filter(self.model.timestamp >= cutoff_time)
            .order_by(self.model.timestamp.desc())
            .all()
        )

    def get_logs_by_date_range(
        self, start_date: datetime, end_date: datetime, vault_id: Optional[int] = None
    ) -> List[Log]:
        """Get logs within a specific date range, optionally filtered by vault"""
        query = self.db.query(self.model).filter(
            self.model.timestamp >= start_date,
            self.model.timestamp <= end_date 
        )
        
        if vault_id:
            query = query.filter(self.model.vault_id == vault_id)
        
        return query.order_by(self.model.timestamp.desc()).all()

    def get_failed_attempts_by_vault(self, vault_id: int, hours: int = 24) -> List[Log]:
        """Get recent failed attempts for a specific vault"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(self.model)
            .filter(
                self.model.vault_id == vault_id,
                self.model.event_type == LogEventType.failed_attempt,
                self.model.timestamp >= cutoff_time
            )
            .order_by(self.model.timestamp.desc())
            .all()
        )

    def get_security_events(self, vault_id: Optional[int] = None, hours: int = 24) -> List[Log]:
        """Get security-related events (failed attempts, tamper, alarm)"""
        security_events = [
            LogEventType.failed_attempt,
            LogEventType.tamper,
            LogEventType.alarm
        ]
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(self.model).filter(
            self.model.event_type.in_(security_events),
            self.model.timestamp >= cutoff_time
        )
        
        if vault_id:
            query = query.filter(self.model.vault_id == vault_id)
        
        return query.order_by(self.model.timestamp.desc()).all()

    def count_events_by_type(self, vault_id: Optional[int] = None, hours: int = 24) -> dict:
        """Get count of events by type for analytics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(self.model.event_type, func.count(self.model.id)).filter(
            self.model.timestamp >= cutoff_time
        )
        
        if vault_id:
            query = query.filter(self.model.vault_id == vault_id)
        
        results = query.group_by(self.model.event_type).all()
        return {event_type: count for event_type, count in results}

    def log_vault_unlock(self, vault_id: int, user_id: int, details: Optional[str] = None) -> Log:
        """Convenience method to log a vault unlock"""
        return self.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=details
        )

    def log_failed_attempt(self, vault_id: int, user_id: Optional[int] = None, details: Optional[str] = None) -> Log:
        """Convenience method to log a failed unlock attempt"""
        return self.create(
            vault_id=vault_id,
            user_id=user_id,
            event_type=LogEventType.failed_attempt,
            details=details
        )

    def log_tamper_event(self, vault_id: int, details: Optional[str] = None) -> Log:
        """Convenience method to log a tamper event"""
        return self.create(
            vault_id=vault_id,
            user_id=None,
            event_type=LogEventType.tamper,
            details=details
        )

    def log_alarm_event(self, vault_id: int, details: Optional[str] = None) -> Log:
        """Convenience method to log an alarm event"""
        return self.create(
            vault_id=vault_id,
            user_id=None,
            event_type=LogEventType.alarm,
            details=details
        )

    def get_logs_with_pagination(
        self,
        page: int = 1,
        per_page: int = 20,
        vault_id: Optional[int] = None,
        event_type: Optional[LogEventType] = None
    ) -> List[Log]:
        """Get paginated logs with optional filters"""
        query = self.db.query(self.model)
        
        if vault_id:
            query = query.filter(self.model.vault_id == vault_id)
        
        if event_type:
            query = query.filter(self.model.event_type == event_type)
        
        offset = (page - 1) * per_page
        return (
            query
            .order_by(self.model.timestamp.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

    def get_filtered_logs_by_vault(self, vault_id: int, prefixes: List[str]) -> List[Log]:
        """
        Get logs for a vault filtered by details prefixes (starts with any prefix).
        
        Args:
            vault_id (int): Vault ID to filter by.
            prefixes (List[str]): List of prefixes to match in details (e.g., ['Locked', 'Tamper']).
            
        Returns:
            List[Log]: Matching logs ordered by timestamp descending.
        """
        if not prefixes:
            return []
        
        from sqlalchemy import or_
        like_filters = [self.model.details.like(f"{prefix}%") for prefix in prefixes]
        
        return (
            self.db.query(self.model)
            .filter(
                self.model.vault_id == vault_id,
                or_(*like_filters)
            )
            .order_by(self.model.timestamp.desc())
            .all()
        )

    def delete_old_logs(self, days: int = 90) -> int:
        """Delete logs older than specified days (for maintenance)"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = (
            self.db.query(self.model)
            .filter(self.model.timestamp < cutoff_date)
            .delete()
        )
        self.db.commit()
        return deleted_count