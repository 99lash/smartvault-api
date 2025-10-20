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
        offset: Optional[int] = None  # ✅ ADD THIS - this was missing!
    ) -> List[dict]:
        """
        Retrieve logs for a specific device filtered by details prefixes.

        Only includes rows where details starts with any of the provided prefixes.

        Args:
            device_id (str): The device ID to filter logs by.
            prefixes (List[str]): List of prefixes to match (e.g., ['DUAL', 'Tamper', 'Failure', 'Manual']).
            limit (Optional[int]): Maximum number of logs to return (None for all).
            offset (Optional[int]): Number of logs to skip (default: 0).

        Returns:
            List[dict]: List of serialized log dictionaries, ordered by timestamp descending.
        """
        if not prefixes:
            return []

        # ✅ Pass offset to repository
        logs = self.repo.get_filtered_logs_by_device(device_id, prefixes, limit, offset)

        # Serialize logs to dictionaries
        serialized_logs = []
        for log in logs:
            log_dict = {
                'id': log.id,
                'device_id': log.device_id,
                'vault_id': log.vault_id,
                'user_id': log.user_id,
                'event_type': log.event_type.value if hasattr(log.event_type, 'value') else log.event_type,
                'details': log.details,
                'timestamp': log.created_at.isoformat() + 'Z' if log.created_at else None
            }
            serialized_logs.append(log_dict)

        return serialized_logs