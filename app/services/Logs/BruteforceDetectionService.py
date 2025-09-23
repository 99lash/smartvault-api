from typing import Optional
from datetime import timedelta
import redis
from app.repositories.LogRepository import LogRepository
from app.models.Log import LogEventType
from sqlalchemy.orm import Session


BRUTEFORCE_THRESHOLD: int = 3
BRUTEFORCE_TTL_SECONDS: int = 600  # 10 minutes


class BruteforceDetectionService:
    """
    Service for detecting and handling bruteforce attacks on NFC and PIN authentication.
    
    Tracks separate failure counts for NFC and PIN methods using Redis for atomicity and TTL-based expiration.
    Integrates with LogRepository for tamper event logging.
    
    Follows SOC: Handles state management and threshold checks independently of auth flows.
    """
    
    def __init__(self, redis_client: redis.Redis, db: Session):
        """
        Initialize the service with Redis client and DB session.
        
        Args:
            redis_client: Redis client for counter storage.
            db: SQLAlchemy session for logging tamper events.
        """
        self.redis_client = redis_client
        self.db = db
        self.repo = LogRepository(db)
    
    def _get_key(self, vault_id: int, method: str) -> str:
        """
        Generate Redis key for failure count.
        
        Args:
            vault_id: The vault ID.
            method: 'nfc' or 'pin'.
            
        Returns:
            str: Redis key like 'bruteforce_nfc_vault_123'.
        """
        return f"bruteforce_{method}_vault_{vault_id}"
    
    def increment_failure_count(self, vault_id: int, method: str) -> int:
        """
        Atomically increment failure count and set TTL if first increment.
        
        Args:
            vault_id: The vault ID.
            method: 'nfc' or 'pin'.
            
        Returns:
            int: New failure count.
        """
        key = self._get_key(vault_id, method)
        count = self.redis_client.incr(key)
        if count == 1:
            self.redis_client.expire(key, BRUTEFORCE_TTL_SECONDS)
        return count
    
    def get_failure_count(self, vault_id: int, method: str) -> int:
        """
        Retrieve current failure count.
        
        Args:
            vault_id: The vault ID.
            method: 'nfc' or 'pin'.
            
        Returns:
            int: Current count (0 if key expired/missing).
        """
        key = self._get_key(vault_id, method)
        return self.redis_client.get(key) or 0
    
    def reset_failure_count(self, vault_id: int, method: str) -> None:
        """
        Reset (delete) failure count for a method.
        
        Args:
            vault_id: The vault ID.
            method: 'nfc' or 'pin'.
        """
        key = self._get_key(vault_id, method)
        self.redis_client.delete(key)
    
    def check_threshold_and_log_tamper(self, vault_id: int, method: str, threshold: int = BRUTEFORCE_THRESHOLD) -> bool:
        """
        Increment count, check threshold, and log tamper if exceeded.
        
        Args:
            vault_id: The vault ID.
            method: 'nfc' or 'pin'.
            threshold: Failure threshold (default: 3).
            
        Returns:
            bool: True if tamper detected (threshold hit), False otherwise.
        """
        count = self.increment_failure_count(vault_id, method)
        if count >= threshold:
            details = "Bruteforce"
            self.repo.log_tamper_event(vault_id=vault_id, details=details)
            # Optional: Lock out by resetting or setting a global lock key
            return True
        return False