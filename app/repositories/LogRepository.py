from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta
from typing import List, Optional
from .Repository import Repository
from app.models.Log import Log, LogEventType


class LogRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, Log)

    def get_by_device(self, device_id: str) -> List[Log]:
        """Get all logs for a specific device"""
        return self.db.query(self.model).filter(self.model.device_id == device_id).all()

    def get_by_user(self, user_id: int) -> List[Log]:
        """Get all logs for a specific user"""
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()

    def get_by_event_type(self, event_type: LogEventType) -> List[Log]:
        """Get all logs of a specific event type"""
        return self.db.query(self.model).filter(self.model.event_type == event_type).all()

    def get_by_device_and_event_type(self, device_id: str, event_type: LogEventType) -> List[Log]:
        """Get logs for a specific device and event type"""
        return (
            self.db.query(self.model)
            .filter(self.model.device_id == device_id, self.model.event_type == event_type)
            .all()
        )

    def get_recent_logs(self, hours: int = 24) -> List[Log]:
        """Get logs from the last N hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(self.model)
            .filter(self.model.created_at >= cutoff_time)
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_logs_by_date_range(
        self, start_date: datetime, end_date: datetime, device_id: Optional[str] = None
    ) -> List[Log]:
        """Get logs within a specific date range, optionally filtered by device"""
        query = self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        )

        if device_id:
            query = query.filter(self.model.device_id == device_id)

        return query.order_by(self.model.created_at.desc()).all()

    def get_failed_attempts_by_device(self, device_id: str, hours: int = 24) -> List[Log]:
        """Get recent failed attempts for a specific device"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.db.query(self.model)
            .filter(
                self.model.device_id == device_id,
                self.model.event_type == LogEventType.failed_attempt,
                self.model.created_at >= cutoff_time
            )
            .order_by(self.model.created_at.desc())
            .all()
        )

    def get_security_events(self, device_id: Optional[str] = None, hours: int = 24) -> List[Log]:
        """Get security-related events (failed attempts, tamper, alarm)"""
        security_events = [
            LogEventType.failed_attempt,
            LogEventType.tamper,
            LogEventType.alarm
        ]
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = self.db.query(self.model).filter(
            self.model.event_type.in_(security_events),
            self.model.created_at >= cutoff_time
        )

        if device_id:
            query = query.filter(self.model.device_id == device_id)

        return query.order_by(self.model.created_at.desc()).all()

    def count_events_by_type(self, device_id: Optional[str] = None, hours: int = 24) -> dict:
        """Get count of events by type for analytics"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = self.db.query(self.model.event_type, func.count(self.model.id)).filter(
            self.model.created_at >= cutoff_time
        )

        if device_id:
            query = query.filter(self.model.device_id == device_id)

        results = query.group_by(self.model.event_type).all()
        return {event_type: count for event_type, count in results}

    def log_device_unlock(self, device_id: str, user_id: int, details: Optional[str] = None) -> Log:
        """Convenience method to log a device unlock"""
        return self.create(
            device_id=device_id,
            user_id=user_id,
            event_type=LogEventType.unlock,
            details=details
        )

    def log_failed_attempt(self, device_id: str, user_id: Optional[int] = None, details: Optional[str] = None, vault_id: Optional[int] = None) -> Log:
        """Convenience method to log a failed unlock attempt"""
        return self.create(
            device_id=device_id,
            user_id=user_id,
            event_type=LogEventType.failed_attempt,
            details=details,
            vault_id=vault_id
        )

    def log_tamper_event(self, device_id: str, details: Optional[str] = None, vault_id: Optional[int] = None) -> Log:
        """Convenience method to log a tamper event"""
        return self.create(
            device_id=device_id,
            user_id=None,
            event_type=LogEventType.tamper,
            details=details,
            vault_id=vault_id
        )

    def log_alarm_event(self, device_id: str, details: Optional[str] = None, vault_id: Optional[int] = None) -> Log:
        """Convenience method to log an alarm event"""
        return self.create(
            device_id=device_id,
            user_id=None,
            event_type=LogEventType.alarm,
            details=details,
            vault_id=vault_id
        )

    def get_logs_with_pagination(
        self,
        page: int = 1,
        per_page: int = 20,
        device_id: Optional[str] = None,
        event_type: Optional[LogEventType] = None
    ) -> List[Log]:
        """Get paginated logs with optional filters"""
        query = self.db.query(self.model)

        if device_id:
            query = query.filter(self.model.device_id == device_id)

        if event_type:
            query = query.filter(self.model.event_type == event_type)

        offset = (page - 1) * per_page
        return (
            query
            .order_by(self.model.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

    def get_filtered_logs_by_device(
        self, 
        device_id: str, 
        prefixes: List[str], 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Log]:
        """
        Get logs for a device filtered by details prefixes (starts with any prefix).
        Includes user relationship for username access.

        Args:
            device_id (str): Device ID to filter by.
            prefixes (List[str]): List of prefixes to match in details (e.g., ['Locked', 'Tamper']).
            limit (Optional[int]): Maximum number of logs to return (None for all).
            offset (Optional[int]): Number of logs to skip (default: 0).

        Returns:
            List[Log]: Matching logs with user relationship loaded, ordered by timestamp descending.
        """
        if not prefixes:
            return []

        like_filters = [self.model.details.like(f"{prefix}%") for prefix in prefixes]

        # Build the base query with user relationship
        from sqlalchemy.orm import joinedload
        query = (
            self.db.query(self.model)
            .options(joinedload(self.model.user))  # Eager load user relationship
            .filter(
                self.model.device_id == device_id,
                or_(*like_filters)
            )
            .order_by(self.model.created_at.desc())
        )

        # ✅ Apply offset if specified
        if offset is not None and offset > 0:
            query = query.offset(offset)

        # Apply limit if specified
        if limit is not None:
            query = query.limit(limit)
        else:
            query = query.limit(50)  # Default limit to prevent excessive data

        # Execute query
        logs = query.all()
        return logs

    def delete_old_logs(self, days: int = 90) -> int:
        """Delete logs older than specified days (for maintenance)"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = (
            self.db.query(self.model)
            .filter(self.model.created_at < cutoff_date)
            .delete()
        )
        self.db.commit()
        return deleted_count

    def bulk_delete(self, filters: list = None) -> int:
        """
        Bulk delete logs based on filter conditions.

        Args:
            filters (list): List of SQLAlchemy filter conditions

        Returns:
            int: Number of records deleted
        """
        if filters is None:
            filters = []

        # Build query with filters
        query = self.db.query(self.model)
        if filters:
            for filter_condition in filters:
                query = query.filter(filter_condition)

        # Execute bulk delete
        deleted_count = query.delete(synchronize_session=False)
        self.db.commit()

        return deleted_count