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
from sqlalchemy import func, and_, or_
from fastapi import HTTPException, status
from app.models.Log import Log, LogEventType
from app.repositories.LogRepository import LogRepository
from app.services.logs.LogQueryService import LogQueryService


class SimpleCache:
    """Simple in-memory cache with TTL for access statistics."""

    def __init__(self, ttl_minutes: int = 5):
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl_minutes = ttl_minutes

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.utcnow() - timestamp < timedelta(minutes=self.ttl_minutes):
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
        self.cache[key] = (value, datetime.utcnow())

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
        self.cache = SimpleCache(ttl_minutes=5)  # 5-minute cache for statistics

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

            self.logger.debug(f"Getting access count by user with filters: user_id={user_id}, vault_id={vault_id}, include_failed={include_failed}")

            # Determine which event types to include
            event_types = self.SUCCESS_EVENTS.copy()
            if include_failed:
                event_types.extend(self.FAILED_EVENTS)

            # Build query filters
            filters = [Log.event_type.in_(event_types)]

            if user_id:
                filters.append(Log.user_id == user_id)
            if vault_id:
                filters.append(Log.vault_id == vault_id)
            if start_date:
                filters.append(Log.created_at >= start_date)
            if end_date:
                filters.append(Log.created_at <= end_date)

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
            self.logger.debug(f"Cached result for user access counts: {cache_key}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting access count by user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve user access counts: {str(e)}"
            )

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
            # Define access event types
            success_events = [LogEventType.unlock, LogEventType.access_granted]
            failed_events = [LogEventType.failed_attempt] if include_failed else []

            event_types = success_events + failed_events

            # Build query filters
            filters = [Log.event_type.in_(event_types)]

            if vault_id:
                filters.append(Log.vault_id == vault_id)
            if start_date:
                filters.append(Log.created_at >= start_date)
            if end_date:
                filters.append(Log.created_at <= end_date)

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
            # Define access event types
            success_events = [LogEventType.unlock, LogEventType.access_granted]
            failed_events = [LogEventType.failed_attempt] if include_failed else []

            event_types = success_events + failed_events

            # Build query filters
            filters = [Log.event_type.in_(event_types)]

            if device_id:
                filters.append(Log.device_id == device_id)
            if start_date:
                filters.append(Log.created_at >= start_date)
            if end_date:
                filters.append(Log.created_at <= end_date)

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
    ) -> Dict[datetime, int]:
        """
        Get daily access trends for the last N days.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            days (int): Number of days to look back

        Returns:
            Dict[datetime, int]: Dictionary with date as key and access count as value
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Define access event types (only successful accesses for trends)
            event_types = [LogEventType.unlock, LogEventType.access_granted]

            # Build query filters
            filters = [
                Log.event_type.in_(event_types),
                Log.created_at >= start_date
            ]

            if vault_id:
                filters.append(Log.vault_id == vault_id)
            if user_id:
                filters.append(Log.user_id == user_id)

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
                # Parse date string to date object and convert to datetime at start of day
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
        days: int = 7
    ) -> Dict[int, int]:
        """
        Get hourly access patterns for the last N days.

        Args:
            vault_id (Optional[int]): Specific vault ID to filter by
            user_id (Optional[int]): Specific user ID to filter by
            days (int): Number of days to look back

        Returns:
            Dict[int, int]: Dictionary with hour (0-23) as key and access count as value
        """
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            # Define access event types (only successful accesses)
            event_types = [LogEventType.unlock, LogEventType.access_granted]

            # Build query filters
            filters = [
                Log.event_type.in_(event_types),
                Log.created_at >= start_date
            ]

            if vault_id:
                filters.append(Log.vault_id == vault_id)
            if user_id:
                filters.append(Log.user_id == user_id)

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
        limit: int = 100
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
            # Build query filters
            filters = [Log.event_type == LogEventType.failed_attempt]

            if vault_id:
                filters.append(Log.vault_id == vault_id)
            if user_id:
                filters.append(Log.user_id == user_id)
            if start_date:
                filters.append(Log.created_at >= start_date)
            if end_date:
                filters.append(Log.created_at <= end_date)

            # Execute query
            results = self.db.query(Log).filter(
                and_(*filters)
            ).order_by(
                Log.created_at.desc()
            ).limit(limit).all()

            # Convert to dictionaries with user information
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
            # Query for the most recent successful access log for this user-vault pair
            result = self.db.query(Log.created_at).filter(
                Log.user_id == user_id,
                Log.vault_id == vault_id,
                Log.event_type.in_(self.SUCCESS_EVENTS)
            ).order_by(Log.created_at.desc()).first()

            return result.created_at if result else None

        except Exception as e:
            self.logger.error(f"Error getting last access timestamp for user {user_id} in vault {vault_id}: {str(e)}")
            raise

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

        Returns:
            Dict: Comprehensive access summary
        """
        try:
            # Log the request parameters for debugging
            self.logger.info(f"get_access_summary called with vault_id={vault_id}, user_id={user_id}, start_date={start_date}, end_date={end_date}, days={days}")

            # Calculate date range if not provided
            if not start_date or not end_date:
                # Use local time for consistency with log creation (Model.py uses datetime.now() which is local)
                if days:
                    end_date_calc = datetime.now()  # Local time
                    start_date_calc = end_date_calc - timedelta(days=days)
                    self.logger.info(f"Calculated date range using days={days}: start_date={start_date_calc}, end_date={end_date_calc}")
                else:
                    end_date_calc = datetime.now()  # Local time
                    start_date_calc = end_date_calc - timedelta(days=7)  # Default 7 days
                    self.logger.info(f"Calculated default date range using local time: start_date={start_date_calc}, end_date={end_date_calc}")
                start_date = start_date or start_date_calc
                end_date = end_date or end_date_calc
            else:
                self.logger.info(f"Using provided date range: start_date={start_date} ({start_date.tzinfo if hasattr(start_date, 'tzinfo') else 'naive'}), end_date={end_date} ({end_date.tzinfo if hasattr(end_date, 'tzinfo') else 'naive'})")

            # Get successful accesses
            self.logger.info(f"Getting successful accesses for vault_id={vault_id}, start_date={start_date}, end_date={end_date}")
            successful_accesses = self.get_access_count_by_vault(
                vault_id=vault_id,
                start_date=start_date,
                end_date=end_date,
                include_failed=False
            )
            self.logger.info(f"Successful accesses result: {successful_accesses}")

            # Get failed attempts
            self.logger.info(f"Getting failed attempts for vault_id={vault_id}, user_id={user_id}, start_date={start_date}, end_date={end_date}")
            failed_attempts_list = self.get_failed_access_attempts(
                vault_id=vault_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=1000  # High limit to get all in period
            )
            failed_attempts = len(failed_attempts_list) if failed_attempts_list else 0
            self.logger.info(f"Failed attempts count: {failed_attempts}")
            # Calculate totals
            successful_count = sum(successful_accesses.values()) if successful_accesses else 0
            total_attempts = successful_count + failed_attempts
            success_rate = (successful_count / total_attempts * 100) if total_attempts > 0 else 0.0
            self.logger.info(f"Calculated totals: successful_count={successful_count}, failed_attempts={failed_attempts}, total_attempts={total_attempts}, success_rate={success_rate}")

            # Get daily trends
            self.logger.info("Getting daily trends")
            daily_trends = self.get_daily_access_trends(
                vault_id=vault_id,
                user_id=user_id,
                days=7
            )
            self.logger.info(f"Daily trends result: {len(daily_trends)} entries")

            # Get hourly patterns
            self.logger.info("Getting hourly patterns")
            hourly_patterns = self.get_hourly_access_patterns(
                vault_id=vault_id,
                user_id=user_id,
                days=7
            )
            self.logger.info(f"Hourly patterns result: {len(hourly_patterns)} entries")

            period = {}
            if start_date:
                period['start_date'] = start_date.isoformat()
            if end_date:
                period['end_date'] = end_date.isoformat()

            # Get recent activity (both successful and failed)
            recent_activities = self.get_recent_activity(
                vault_id=vault_id,
                limit=10
            )

            result = {
                'successful_accesses': successful_accesses or {},
                'failed_attempts': failed_attempts,
                'total_attempts': total_attempts,
                'success_rate': round(success_rate, 2),
                'daily_trends': daily_trends or {},
                'hourly_patterns': hourly_patterns or {},
                'period': period,
                'recent_activity': recent_activities
            }
            self.logger.info(f"Returning access summary: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Error getting access summary: {str(e)}")
            raise

    def get_recent_activity(
        self,
        vault_id: Optional[int] = None,
        limit: int = 10
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
            activities = []

            # Get recent successful unlocks with user information
            success_filters = [
                Log.event_type.in_(self.SUCCESS_EVENTS),
                Log.created_at >= datetime.now() - timedelta(days=7)  # Last 7 days
            ]
            if vault_id:
                success_filters.append(Log.vault_id == vault_id)

            success_logs = self.db.query(Log).join(Log.user).filter(  # Join with User table
                and_(*success_filters)
            ).order_by(Log.created_at.desc()).limit(limit // 2).all()  # Half for success, half for failed

            # Get recent failed attempts with user information
            failed_filters = [
                Log.event_type.in_(self.FAILED_EVENTS),
                Log.created_at >= datetime.now() - timedelta(days=7)  # Last 7 days
            ]
            if vault_id:
                failed_filters.append(Log.vault_id == vault_id)

            failed_logs = self.db.query(Log).outerjoin(Log.user).filter(  # Left join with User table (failed attempts might not have users)
                and_(*failed_filters)
            ).order_by(Log.created_at.desc()).limit(limit // 2).all()  # Half for failed

            # Convert successful logs to activity format
            for log in success_logs:
                # Get username from user relationship if available
                username = 'Unknown User'
                if log.user and log.user.username:
                    username = log.user.username
                elif log.user_id:
                    username = f'User {log.user_id}'

                activity = {
                    'id': log.id,
                    'type': 'success',
                    'title': 'Successful Access',
                    'description': f'Vault accessed successfully',
                    'timestamp': log.created_at.isoformat(),
                    'user': username,
                    'event_type': log.event_type.value,
                    'details': log.details
                }
                activities.append(activity)

            # Convert failed logs to activity format
            for log in failed_logs:
                # Get username from user relationship if available
                username = 'Unknown User'
                if log.user and log.user.username:
                    username = log.user.username
                elif log.user_id:
                    username = f'User {log.user_id}'

                activity = {
                    'id': log.id,
                    'type': 'failed',
                    'title': 'Failed Access Attempt',
                    'description': f'Unauthorized access attempt detected',
                    'timestamp': log.created_at.isoformat(),
                    'user': username,
                    'event_type': log.event_type.value,
                    'details': log.details
                }
                activities.append(activity)

            # Sort by timestamp (most recent first)
            activities.sort(key=lambda x: x['timestamp'], reverse=True)

            # Return only the requested limit
            return activities[:limit]

        except Exception as e:
            self.logger.error(f"Error getting recent activity: {str(e)}")
            return []