from typing import List, Optional  # ✅ Only need one import line
from sqlalchemy.orm import Session
from app.repositories.LogRepository import LogRepository
from app.models.Log import Log

class LogQueryService:
    """
    Dedicated service for read-only query operations on logs.
    
    Focuses on retrieving and filtering log data without modifying state.
    Delegates to LogRepository for database interactions.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the LogQueryService with a database session.
        
        Args:
            db (Session): SQLAlchemy database session.
        """
        self.repo = LogRepository(db)
    
    def get_filtered_logs_by_device(
        self, 
        device_id: str, 
        prefixes: List[str], 
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[dict]:
        """
        Retrieve logs for a specific device filtered by details prefixes.

        Only includes rows where details starts with any of the provided prefixes.
        Includes username information for better user identification.

        Args:
            device_id (str): The device ID to filter logs by.
            prefixes (List[str]): List of prefixes to match (e.g., ['DUAL', 'Tamper', 'Failure', 'Manual']).
            limit (Optional[int]): Maximum number of logs to return (None for all).
            offset (Optional[int]): Number of logs to skip (default: 0).

        Returns:
            List[dict]: List of serialized log dictionaries with username, ordered by timestamp descending.
        """
        if not prefixes:
            return []

        # Get logs with user relationship loaded
        logs = self.repo.get_filtered_logs_by_device(device_id, prefixes, limit, offset)

        # Serialize logs to dictionaries with username
        serialized_logs = []
        for log in logs:
            # Determine username with proper fallback logic
            username = self._get_username_for_log(log)
            
            log_dict = {
                'id': log.id,
                'device_id': log.device_id,
                'vault_id': log.vault_id,
                'user_id': log.user_id,
                'username': username,
                'event_type': log.event_type.value if hasattr(log.event_type, 'value') else log.event_type,
                'details': log.details,
                'timestamp': log.created_at.isoformat() + 'Z' if log.created_at else None
            }
            serialized_logs.append(log_dict)

        return serialized_logs

    def _get_username_for_log(self, log) -> str:
        """
        Extract username from log with proper fallback logic.
        
        Args:
            log: Log object with potential user relationship
            
        Returns:
            str: Username or appropriate fallback
        """
        # Check if user relationship is loaded and user exists
        if hasattr(log, 'user') and log.user:
            return log.user.username or f"User {log.user_id}"
        
        # Fallback for system events (no user_id)
        if not log.user_id:
            return "System"
        
        # Fallback for missing user relationship
        return f"User {log.user_id}"