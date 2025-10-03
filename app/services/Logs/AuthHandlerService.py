from typing import Dict, Optional
from app.services.Logs.LogService import LogService
from app.schemas.log import LogCreate
from app.models.Log import Log

class AuthHandlerService:
    def __init__(self, log_service: LogService):
        self.log_service = log_service

    def handle_unlock_request(self, payload: LogCreate) -> Dict:
        """
        Handle unlock request and return response dict for WebSocket/HTTP.
        
        Args:
            payload: The unlock event.
        
        Returns:
            Dict: Formatted response (status, event_type, message, user_id).
        """
        log_entry, status = self.log_service.validate_progressive_access(
            str(payload.vault_id), payload.details
        )
        
        # Response mapping
        response_map = {
            'unlock': {
                "status": "ok",
                "event_type": "unlock",
                "message": "Access granted"
            },
            'pending': {
                "status": "pending",
                "event_type": "pending",
                "message": "First factor accepted, provide second factor"
            },
            'no_access': {
                "status": "no_access",
                "event_type": "tamper",
                "message": "Access denied - insufficient permissions"
            },
            'invalid_credentials': {
                "status": "invalid_credentials",
                "event_type": "failed_attempt",
                "message": "Invalid credentials"
            } 
        }
        
        if status in response_map:
            resp = response_map[status].copy()
            if status in ['unlock', 'pending']:
                resp["user_id"] = log_entry.user_id if log_entry else None
            else:
                resp["user_id"] = None
            
            # Customizations
            if status == 'unlock' and log_entry and 'DUAL' in log_entry.details:
                resp["message"] = "Dual authentication successful"
            if status == 'invalid_credentials' and log_entry and "Same factor repeated" in log_entry.details:
                resp["message"] = "Invalid second factor or same factor repeated"
            if status == 'invalid_credentials':
                self.log_service.clear_sessions_for_vault(str(payload.vault_id))
            return resp
        else:
            return {"status": "error", "message": f"Unknown status: {status}"}