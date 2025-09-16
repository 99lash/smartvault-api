from typing import List
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
    
    def get_filtered_logs_by_vault(self, vault_id: int, prefixes: List[str]) -> List[dict]:
        """
        Retrieve logs for a specific vault filtered by details prefixes.
        
        Only includes rows where details starts with any of the provided prefixes.
        
        Args:
            vault_id (int): The vault ID to filter logs by.
            prefixes (List[str]): List of prefixes to match (e.g., ['DUAL', 'Tamper', 'Failure', 'Manual']).
        
        Returns:
            List[dict]: List of serialized log dictionaries, ordered by timestamp descending.
        """
        if not prefixes:
            return []  # No prefixes provided, return empty list
        
        logs = self.repo.get_filtered_logs_by_vault(vault_id, prefixes)
        
        # Serialize logs to dictionaries (exclude internal SQLAlchemy attributes)
        serialized_logs = []
        for log in logs:
            log_dict = {
                'id': log.id,
                'vault_id': log.vault_id,
                'user_id': log.user_id,
                'event_type': log.event_type.value if hasattr(log.event_type, 'value') else log.event_type,
                'details': log.details,
                'timestamp': log.timestamp.isoformat() if log.timestamp else None
            }
            serialized_logs.append(log_dict)
        
        return serialized_logs