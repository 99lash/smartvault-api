from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ValidateAccessRequest(BaseModel):
    # vault_id: int
    device_id: str
    details: str

class WSQueryRequest(BaseModel):
    """
    Pydantic model for WebSocket query request.
    Used to validate incoming parameters for filtered log queries.
    """
    # vault_id: int
    device_id: str
    prefixes: List[str] = ["DUAL", "Tamper", "Failure", "Manual"]  # Default prefixes

class LogResponse(BaseModel):
    """
    Response model for serialized log entries.
    Ensures consistent output for API/WS responses.
    """
    id: int
    # vault_id: int
    device_id: str
    user_id: Optional[int] = None
    username: Optional[str] = None  # Added username field
    event_type: str
    details: str
    timestamp: datetime