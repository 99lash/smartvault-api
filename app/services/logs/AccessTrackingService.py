"""
Access Tracking Service

Analyzes log data to provide insights into access patterns and usage statistics.
Tracks successful accesses, failed attempts, and access trends over time.

Features:
- Count accesses by user, vault, device, and time periods
- Generate daily and hourly access trends
- Monitor failed access attempts for security
- Provide comprehensive access summaries
- Support filtering by date ranges and specific entities
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.Log import Log, LogEventType
from app.repositories.LogRepository import LogRepository
from app.services.logs.LogQueryService import LogQueryService


# Constants
DEFAULT_CACHE_TTL_MINUTES = 5
DEFAULT_TREND_DAYS = 7
DEFAULT_HOURLY_PATTERN_DAYS = 7
DEFAULT_RECENT_ACTIVITY_DAYS = 7
DEFAULT_RECENT_ACTIVITY_LIMIT = 10
DEFAULT_FAILED_ATTEMPTS_LIMIT = 100
HIGH_FAILED_ATTEMPTS_LIMIT = 1000


class SimpleCache:
    """Simple in-memory cache with TTL for access statistics."""

    def __init__(self, ttl_minutes: int = DEFAULT_CACHE_TTL_MINUTES):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl_minutes = ttl_minutes

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(minutes=self.ttl_minutes):
                logging.getLogger(__name__).debug(f"Cache hit for key: {key}")
                return value
            else:
                # Expired, remove from cache
                logging.getLogger(__name__).debug(f"Cache expired for key: {key}")
                del self.cache[key]
        logging.getLogger(__name__).debug(f"Cache miss for key: {key}")
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp."""
        logging.getLogger(__name__).debug(f"Setting cache for key: {key}")
        self.cache[key] = (value, datetime.now())

    def clear(self) -> None:
        """Clear all cached values."""
        self.cache.clear()


class AccessTrackingService:
    """
    Service for tracking and analyzing access patterns from log data.

    Provides methods to count accesses by user, vault, device, and time periods.
    Supports both successful accesses and failed attempts for security monitoring.
    """

    def __init__(self, db: Session):
        """
        Initialize the AccessTrackingService with database session.

        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db
        self.repo = LogRepository(db)
        self.query_service = LogQueryService(db)
        self.logger = logging.getLogger(__name__)
        self.cache = SimpleCache(ttl_minutes=DEFAULT_CACHE_TTL_MINUTES)

        # Define access event types for consistent filtering
        self.SUCCESS_EVENTS = [LogEventType.unlock, LogEventType.access_granted]
        self.FAILED_EVENTS = [LogEventType.failed_attempt]
        self.ALL_ACCESS_EVENTS = self.SUCCESS_EVENTS + self.FAILED_EVENTS

    def _parse_date_string(self, date_obj) -> date:
        """
        Parse a date object or string to a date object.

        Args:
            date_obj: Date object or string from database query.

        Returns:
            date: Parsed date object.

        Raises:
            ValueError: If the date format is invalid.
        """
        if isinstance(date_obj, str):
            # Handle both date-only strings and datetime strings
            try:
                return date.fromisoformat(date_obj)
            except ValueError:
                # If it's a datetime string, extract just the date part
                if 'T' in date_obj:
                    return date.fromisoformat(date_obj.split('T')[0])
                raise
        elif isinstance(date_obj, date):
            return date_obj
        elif hasattr(date_obj, 'date'):  # datetime object
            return date_obj.date()
        else:
            raise ValueError(f"Invalid date format: {date_obj}")

    def _generate_cache_key(self, method_name: str, **kwargs) -> str:
        """Generate a cache key for the given method and parameters."""
        key_parts = [method_name]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}:{v}")
        return "|".join(key_parts)

    def _build_query_filters(
        self,
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        device_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[LogEventType]] = None
    ) -> List:
        """
        Build query filters for log queries.
        
        Args:
            vault_id: Optional vault ID filter
            user_id: Optional user ID filter
            device_id: Optional device ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            event_types: Optional list of event types to filter
            
        Returns:
            List of SQLAlchemy filter expressions
        """
        filters = []
        
        if event_types:
            filters.append(Log.event_type.in_(event_types))
        
        if vault_id:
            filters.append(Log.vault_id == vault_id)
        if user_id:
            filters.append(Log.user_id == user_id)
        if device_id:
            filters.append(Log.device_id == device_id)
        if start_date:
            filters.append(Log.created_at >= start_date)
        if end_date:
            filters.append(Log.created_at <= end_date)
            
        return filters

    def _get_event_types(self, include_failed: bool = False) -> List[LogEventType]:
        """Get event types based on whether to include failed attempts."""
        event_types = self.SUCCESS_EVENTS.copy()
        if include_failed:
            event_types.extend(self.FAILED_EVENTS)
        return event_types

    def _extract_username(self, log: Log) -> str:
        """
        Extract username from a log entry.
        
        Args:
            log: Log entry
            
        Returns:
            Username string
        """
        if log.user and log.user.username:
            return log.user.username
        elif log.user_id:
            return f'User {log.user_id}'
        return 'Unknown User'

    def _get_current_time(self) -> datetime:
        """
        Get current time using local timezone for consistency.
        
        Returns:
            Current datetime in local timezone
        """
        return datetime.now()

    def get_access_count_by_user(
        self,
        user_id: Optional[int] = None,
        vault_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_failed: bool = False
    ) -> Dict[str, int]:
        """
        Get access counts for a specific user or all users.

        Args:
            user_id (Optional[int]): Specific user ID to filter by
            vault_id (Optional[int]): Specific vault ID to filter by
            start_date (Optional[datetime]): Start date for filtering
            end_date (Optional[datetime]): End date for filtering
            include_failed (bool): Whether to include failed attempts

        Returns:
            Dict[str, int]: Dictionary with user_id as key and access count as value
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                'get_access_count_by_user',
                user_id=user_id,
                vault_id=vault_id,
                start_date=start_date.isoformat() if start_date else None,
                end_date=end_date.isoformat() if end_date else None,
                include_failed=include_failed
            )

            # Check cache first
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                self.logger.debug(f"Cache hit for user access counts: {cache_key}")
                return cached_result

            self.logger.debug(f"Cache miss for user access counts: {cache_key}")

            # Build filters
            event_types = self._get_event_types(include_failed)
            filters = self._build_query_filters(
                user_id=user_id,
                vault_id=vault_id,
                start_date=start_date,
                end_date=end_date,
                event_types=event_types
            )

            # Execute query
            if user_id:
                # Count for specific user
                count = self.db.query(func.count(Log.id)).filter(and_(*filters)).scalar()
                result = {str(user_id): count}
                self.logger.debug(f"Access count for user {user_id}: {count}")
            else:
                # Count for all users
                results = self.db.query(
                    Log.user_id,
                    func.count(Log.id).label('access_count')
                ).filter(
                    and_(*filters)
                ).group_by(Log.user_id).all()

                result = {str(user.user_id): user.access_count for user in results}
                self.logger.debug(f"Access counts for all users: {result}")

            # Cache the result
            self.cache.set(cache_key, result)
            return result

        except Exception as e:
            self.logger.error(f"Error getting access count by user: {str(e)}")
            raise

    def get_access_count_by_vault(
        self,
        vault_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_failed: bool = False
    ) -> Dict[str, int]:
        """
        Get access counts for a specific vault or all vaults.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            start_date (Optional[datetime]): Start date for filtering
            end_date (Optional[datetime]): End date for filtering
            include_failed (bool): Whether to include failed attempts

        Returns:
            Dict[str, int]: Dictionary with vault_id as key and access count as value
        """
        try:
            event_types = self._get_event_types(include_failed)
            filters = self._build_query_filters(
                vault_id=vault_id,
                start_date=start_date,
                end_date=end_date,
                event_types=event_types
            )

            # Execute query
            if vault_id:
                # Count for specific vault
                count = self.db.query(func.count(Log.id)).filter(and_(*filters)).scalar()
                return {str(vault_id): count}
            else:
                # Count for all vaults
                results = self.db.query(
                    Log.vault_id,
                    func.count(Log.id).label('access_count')
                ).filter(
                    and_(*filters)
                ).group_by(Log.vault_id).all()

                return {str(vault.vault_id): vault.access_count for vault in results}

        except Exception as e:
            self.logger.error(f"Error getting access count by vault: {str(e)}")
            raise

    def get_access_count_by_device(
        self,
        device_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_failed: bool = False
    ) -> Dict[str, int]:
        """
        Get access counts for a specific device or all devices.

        Args:
            device_id (Optional[str]): Specific device ID to filter by
            start_date (Optional[datetime]): Start date for filtering
            end_date (Optional[datetime]): End date for filtering
            include_failed (bool): Whether to include failed attempts

        Returns:
            Dict[str, int]: Dictionary with device_id as key and access count as value
        """
        try:
            event_types = self._get_event_types(include_failed)
            filters = self._build_query_filters(
                device_id=device_id,
                start_date=start_date,
                end_date=end_date,
                event_types=event_types
            )

            # Execute query
            if device_id:
                # Count for specific device
                count = self.db.query(func.count(Log.id)).filter(and_(*filters)).scalar()
                return {device_id: count}
            else:
                # Count for all devices
                results = self.db.query(
                    Log.device_id,
                    func.count(Log.id).label('access_count')
                ).filter(
                    and_(*filters)
                ).group_by(Log.device_id).all()

                return {device.device_id: device.access_count for device in results}

        except Exception as e:
            self.logger.error(f"Error getting access count by device: {str(e)}")
            raise

    def get_daily_access_trends(
        self,
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        days: int = 30
    ) -> Dict[str, int]:
        """
        Get daily access trends for the last N days.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            days (int): Number of days to look back

        Returns:
            Dict[str, int]: Dictionary with ISO date string as key and access count as value
        """
        try:
            # Use local time for consistency with log creation
            start_date = self._get_current_time() - timedelta(days=days)

            filters = self._build_query_filters(
                vault_id=vault_id,
                user_id=user_id,
                start_date=start_date,
                event_types=self.SUCCESS_EVENTS
            )

            # Execute query grouped by date
            results = self.db.query(
                func.date(Log.created_at).label('access_date'),
                func.count(Log.id).label('access_count')
            ).filter(
                and_(*filters)
            ).group_by(
                func.date(Log.created_at)
            ).order_by(
                func.date(Log.created_at)
            ).all()

            # Convert to dictionary with ISO string keys
            trends = {}
            for result in results:
                date_obj = self._parse_date_string(result.access_date)
                date_key = datetime.combine(date_obj, datetime.min.time())
                trends[date_key.isoformat()] = result.access_count

            return trends

        except Exception as e:
            self.logger.error(f"Error getting daily access trends: {str(e)}")
            raise

    def get_hourly_access_patterns(
        self,
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        days: int = DEFAULT_HOURLY_PATTERN_DAYS
    ) -> Dict[str, int]:
        """
        Get hourly access patterns for the last N days.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            days (int): Number of days to look back

        Returns:
            Dict[str, int]: Dictionary with hour (0-23) as key and access count as value
        """
        try:
            start_date = self._get_current_time() - timedelta(days=days)

            filters = self._build_query_filters(
                vault_id=vault_id,
                user_id=user_id,
                start_date=start_date,
                event_types=self.SUCCESS_EVENTS
            )

            # Execute query grouped by hour
            results = self.db.query(
                func.extract('hour', Log.created_at).label('access_hour'),
                func.count(Log.id).label('access_count')
            ).filter(
                and_(*filters)
            ).group_by(
                func.extract('hour', Log.created_at)
            ).order_by(
                func.extract('hour', Log.created_at)
            ).all()

            # Convert to dictionary with string keys
            patterns = {str(int(result.access_hour)): result.access_count for result in results}

            return patterns

        except Exception as e:
            self.logger.error(f"Error getting hourly access patterns: {str(e)}")
            raise

    def get_failed_access_attempts(
        self,
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = DEFAULT_FAILED_ATTEMPTS_LIMIT
    ) -> List[Dict]:
        """
        Get failed access attempts for security monitoring.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            start_date (Optional[datetime]): Start date for filtering
            end_date (Optional[datetime]): End date for filtering
            limit (int): Maximum number of results to return

        Returns:
            List[Dict]: List of failed access attempts with details
        """
        try:
            filters = self._build_query_filters(
                vault_id=vault_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                event_types=[LogEventType.failed_attempt]
            )

            # Execute query
            results = self.db.query(Log).filter(
                and_(*filters)
            ).order_by(
                Log.created_at.desc()
            ).limit(limit).all()

            # Convert to dictionaries
            failed_attempts = []
            for log in results:
                attempt = {
                    'id': log.id,
                    'device_id': log.device_id,
                    'vault_id': log.vault_id,
                    'user_id': log.user_id,
                    'username': None,  # Would need to join with User table
                    'event_type': log.event_type.value,
                    'details': log.details,
                    'timestamp': log.created_at.isoformat() + 'Z' if log.created_at else None
                }
                failed_attempts.append(attempt)

            return failed_attempts

        except Exception as e:
            self.logger.error(f"Error getting failed access attempts: {str(e)}")
            raise

    def get_last_access_timestamp(
        self,
        user_id: int,
        vault_id: int
    ) -> Optional[datetime]:
        """
        Get the timestamp of the last successful access for a user in a vault.

        Args:
            user_id (int): User ID to get last access for
            vault_id (int): Vault ID to get last access for

        Returns:
            Optional[datetime]: Timestamp of last access, or None if no access found
        """
        try:
            # Primary query: exact success events match
            result = self.db.query(Log.created_at).filter(
                Log.user_id == user_id,
                Log.vault_id == vault_id,
                Log.event_type.in_(self.SUCCESS_EVENTS)
            ).order_by(Log.created_at.desc()).first()

            if result:
                self.logger.debug(f"Found last access for user {user_id} in vault {vault_id}: {result.created_at}")
                return result.created_at

            # Fallback 1: Include unlock_confirm
            result = self.db.query(Log.created_at).filter(
                Log.user_id == user_id,
                Log.vault_id == vault_id,
                Log.event_type.in_([LogEventType.unlock, LogEventType.access_granted, LogEventType.unlock_confirm])
            ).order_by(Log.created_at.desc()).first()

            if result:
                self.logger.debug(f"Found last access (fallback) for user {user_id} in vault {vault_id}: {result.created_at}")
                return result.created_at

            # Fallback 2: Any access-related event (exclude non-access events)
            result = self.db.query(Log.created_at).filter(
                Log.user_id == user_id,
                Log.vault_id == vault_id,
                ~Log.event_type.in_([LogEventType.disconnected, LogEventType.alarm])
            ).order_by(Log.created_at.desc()).first()

            if result:
                self.logger.debug(f"Found last activity (final fallback) for user {user_id} in vault {vault_id}: {result.created_at}")
                return result.created_at

            self.logger.debug(f"No access logs found for user {user_id} in vault {vault_id}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting last access timestamp for user {user_id} in vault {vault_id}: {str(e)}")
            raise

    def _calculate_date_range(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        days: Optional[int]
    ) -> Tuple[datetime, datetime]:
        """
        Calculate date range for queries.
        
        Args:
            start_date: Optional provided start date
            end_date: Optional provided end date
            days: Optional number of days to look back
            
        Returns:
            Tuple of (start_date, end_date)
        """
        if start_date and end_date:
            return start_date, end_date
            
        end_date_calc = self._get_current_time()
        
        if days:
            start_date_calc = end_date_calc - timedelta(days=days)
        else:
            start_date_calc = end_date_calc - timedelta(days=DEFAULT_TREND_DAYS)
            
        return start_date_calc, end_date_calc

    def _build_activity_from_log(self, log: Log, activity_type: str) -> Dict[str, Any]:
        """
        Build activity dictionary from log entry.
        
        Args:
            log: Log entry
            activity_type: Type of activity ('success' or 'failed')
            
        Returns:
            Activity dictionary
        """
        username = self._extract_username(log)
        
        activity_config = {
            'success': {
                'title': 'Successful Access',
                'description': 'Vault accessed successfully'
            },
            'failed': {
                'title': 'Failed Access Attempt',
                'description': 'Unauthorized access attempt detected'
            }
        }
        
        config = activity_config.get(activity_type, activity_config['success'])
        
        return {
            'id': log.id,
            'type': activity_type,
            'title': config['title'],
            'description': config['description'],
            'timestamp': log.created_at.isoformat(),
            'user': username,
            'event_type': log.event_type.value,
            'details': log.details
        }

    def _get_recent_logs_by_type(
        self,
        event_types: List[LogEventType],
        vault_id: Optional[int],
        days: int,
        limit: int,
        join_user: bool = True
    ) -> List[Log]:
        """
        Get recent logs filtered by event types.
        
        Args:
            event_types: List of event types to filter
            vault_id: Optional vault ID filter
            days: Number of days to look back
            limit: Maximum number of results
            join_user: Whether to join User table
            
        Returns:
            List of Log entries
        """
        cutoff_date = self._get_current_time() - timedelta(days=days)
        
        filters = [
            Log.event_type.in_(event_types),
            Log.created_at >= cutoff_date
        ]
        
        if vault_id:
            filters.append(Log.vault_id == vault_id)
        
        query = self.db.query(Log)
        if join_user:
            query = query.join(Log.user)
        else:
            query = query.outerjoin(Log.user)
            
        return query.filter(
            and_(*filters)
        ).order_by(Log.created_at.desc()).limit(limit).all()

    def get_recent_activity(
        self,
        vault_id: Optional[int] = None,
        limit: int = DEFAULT_RECENT_ACTIVITY_LIMIT
    ) -> List[Dict[str, Any]]:
        """
        Get recent activity for the activity feed, including both successful unlocks and failed attempts.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            limit (int): Maximum number of activities to return

        Returns:
            List[Dict]: List of recent activities formatted for the activity feed
        """
        try:
            # Get recent successful and failed logs
            success_limit = limit // 2
            failed_limit = limit // 2
            
            success_logs = self._get_recent_logs_by_type(
                self.SUCCESS_EVENTS,
                vault_id,
                DEFAULT_RECENT_ACTIVITY_DAYS,
                success_limit,
                join_user=True
            )
            
            failed_logs = self._get_recent_logs_by_type(
                self.FAILED_EVENTS,
                vault_id,
                DEFAULT_RECENT_ACTIVITY_DAYS,
                failed_limit,
                join_user=False
            )

            # Convert to activity format
            activities = []
            for log in success_logs:
                activities.append(self._build_activity_from_log(log, 'success'))
            
            for log in failed_logs:
                activities.append(self._build_activity_from_log(log, 'failed'))

            # Sort by timestamp (most recent first)
            activities.sort(key=lambda x: x['timestamp'], reverse=True)

            # Return only the requested limit
            return activities[:limit]

        except Exception as e:
            self.logger.error(f"Error getting recent activity: {str(e)}")
            return []

    def get_access_summary(
        self,
        vault_id: Optional[int] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive access summary including successful and failed attempts.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            start_date (Optional[datetime]): Start date for filtering
            end_date (Optional[datetime]): End date for filtering
            days (Optional[int]): Number of days to look back if dates not provided

        Returns:
            Dict: Comprehensive access summary
        """
        try:
            self.logger.info(f"get_access_summary called with vault_id={vault_id}, user_id={user_id}, start_date={start_date}, end_date={end_date}, days={days}")

            # Calculate date range
            start_date, end_date = self._calculate_date_range(start_date, end_date, days)
            self.logger.info(f"Using date range: start_date={start_date}, end_date={end_date}")

            # Get successful accesses
            successful_accesses = self.get_access_count_by_vault(
                vault_id=vault_id,
                start_date=start_date,
                end_date=end_date,
                include_failed=False
            )

            # Get failed attempts
            failed_attempts_list = self.get_failed_access_attempts(
                vault_id=vault_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=HIGH_FAILED_ATTEMPTS_LIMIT
            )
            failed_attempts = len(failed_attempts_list) if failed_attempts_list else 0

            # Calculate totals
            successful_count = sum(successful_accesses.values()) if successful_accesses else 0
            total_attempts = successful_count + failed_attempts
            success_rate = (successful_count / total_attempts * 100) if total_attempts > 0 else 0.0

            # Get daily trends
            if days:
                trend_days = days
            elif start_date and end_date:
                trend_days = max(1, (end_date - start_date).days + 1)
            else:
                trend_days = DEFAULT_TREND_DAYS
            
            daily_trends = self.get_daily_access_trends(
                vault_id=vault_id,
                user_id=user_id,
                days=trend_days
            )

            # Get hourly patterns
            hourly_patterns = self.get_hourly_access_patterns(
                vault_id=vault_id,
                user_id=user_id,
                days=DEFAULT_HOURLY_PATTERN_DAYS
            )

            # Get recent activity
            recent_activities = self.get_recent_activity(
                vault_id=vault_id,
                limit=DEFAULT_RECENT_ACTIVITY_LIMIT
            )

            # Build result
            result = {
                'successful_accesses': successful_accesses or {},
                'failed_attempts': failed_attempts,
                'total_attempts': total_attempts,
                'success_rate': round(success_rate, 2),
                'daily_trends': daily_trends or {},
                'hourly_patterns': hourly_patterns or {},
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'recent_activity': recent_activities
            }
            
            self.logger.info(f"Returning access summary with {len(daily_trends)} daily trends and {len(recent_activities)} recent activities")
            return result

        except Exception as e:
            self.logger.error(f"Error getting access summary: {str(e)}")
            raise
