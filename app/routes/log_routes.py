from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from typing import List, Optional
from datetime import datetime
from app.schemas.log import LogCreate, LogRead, LogVaultSummaryRead, LogUserSummaryRead, LogVaultAttackRead, LogVaultSuspiciousRead, LogActivityReportRead, LogStatsRead
from app.schemas.LogSchemas import WSQueryRequest, LogResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.Logs.LogService import LogService
from app.services.Logs.LogQueryService import LogQueryService
from app.websockets.LogWebSocketHandler import LogWebSocketHandler
from app.websockets.QueryWebSocketHandler import QueryWebSocketHandler
from app.models.Log import LogEventType
from app.schemas.Response import Response
from app.core.database import SessionLocal
from pydantic import BaseModel
from app.services.VaultService import VaultService
from app.services.UserService import UserService

class ValidateAccessRequest(BaseModel):
    vault_id: int
    details: str

# -----------------------------
# router for Log endpoints
# -----------------------------
# Handles HTTP/WebSocket requests for log management and real-time authentication events.
# - HTTP: CRUD operations for logs (list, delete)
# - WebSocket: Real-time processing of unlock attempts, tamper detection, etc.
# Delegates business logic to services and handlers for separation of concerns (SOC).
router = APIRouter(prefix="/logs", tags=["logs"])

# -----------------------------
# HTTP Endpoints for Log Management
# -----------------------------
# Basic CRUD operations for retrieving and managing logs.

# -----------------------------
# Retrieve all log entries
# -----------------------------
@router.get("/", response_model=list[LogRead])
def list_logs(db: Session = Depends(get_db)):
    """
    Retrieve all log entries from the database.
    
    This endpoint provides a complete audit trail for all events.
    
    Args:
        db (Session): Database session injected via dependency.
        
    Returns:
        List[dict]: Serialized log records.
    """
    service = LogService(db)
    return service.get_all_logs()

# -----------------------------
# Delete a specific log entry
# -----------------------------
@router.delete("/{log_id}", response_model=Response)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    """
    Delete a log entry by its unique ID.
    
    Use this for administrative cleanup of audit logs (use cautiously in production).
    
    Args:
        log_id (int): The ID of the log to delete.
        db (Session): Database session.
        
    Returns:
        dict: Confirmation message on success.
        
    Raises:
        HTTPException: 404 if the log ID does not exist.
    """
    service = LogService(db)
    log = service.delete_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    return Response(success=True, detail=f"Log {log_id} deleted successfully")

@router.get("/vault/{vault_id}/filtered")
def get_filtered_logs(
    vault_id: int,
    prefixes: str = "DUAL,Tamper,Failure,Manual",
    db: Session = Depends(get_db)
):
    """
    Get logs for a vault filtered by specific details prefixes.
    
    Query Param:
        prefixes: Comma-separated list of prefixes (default: DUAL,Tamper,Failure,Manual).
    
    Returns:
        List[dict]: Filtered and serialized logs, ordered by timestamp descending.
    """
    prefix_list = [p.strip() for p in prefixes.split(",") if p.strip()]
    service = LogQueryService(db)
    logs = service.get_filtered_logs_by_vault(vault_id, prefix_list)
    if not logs:
        raise HTTPException(status_code=404, detail="No matching logs found")
    # Serialize with LogResponse for consistency
    serialized_logs = [LogResponse(**log).model_dump() for log in logs]
    return serialized_logs

# -----------------------------
# WebSocket Endpoint for Real-Time Event Processing
# -----------------------------
# This endpoint handles streaming events from clients (e.g., Arduino devices) for
# real-time authentication, logging, and status updates. Each message is processed
# transactionally with a new DB session to ensure isolation.

@router.websocket("/ws")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket endpoint for real-time log and authentication event processing.
    
    Listens for JSON payloads representing events (e.g., unlock attempts from NFC/PIN).
    Validates, processes via services/handlers, and responds with status (e.g., "pending", "unlock").
    Each message uses a fresh DB session for atomicity.
    
    Args:
        websocket (WebSocket): Connected client (e.g., device sending credentials).
    """
    handler = LogWebSocketHandler(websocket)
    await handler.handle_connection()

@router.websocket("/ws/query")
async def websocket_query_logs(websocket: WebSocket):
    """
    WebSocket endpoint for querying filtered logs.
    
    On connection, expects a JSON payload with vault_id and prefixes.
    Responds with the filtered logs as a JSON array.
    Handles errors and disconnections gracefully.
    
    Args:
        websocket (WebSocket): Connected client requesting logs.
    """
    handler = QueryWebSocketHandler(websocket)
    await handler.handle_connection()