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
from app.models.User import User
from app.schemas.Response import Response
from app.core.database import SessionLocal
from pydantic import BaseModel
from app.services.VaultService import VaultService
from app.services.UserService import UserService
from app.services.Logs.VaultAccessControllerService import VaultAccessController
from app.repositories.UserVaultRepository import UserVaultRepository

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
    current_user: User = Depends(UserService.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get logs for a vault filtered by specific details prefixes.
    
    Query Param:
        prefixes: Comma-separated list of prefixes (default: DUAL,Tamper,Failure,Manual).
    
    Returns:
        List[dict]: Filtered and serialized logs, ordered by timestamp descending.
    """
    # Check vault access
    user_vault_repo = UserVaultRepository(db)
    controller = VaultAccessController(user_vault_repo)
    if not controller.check_access(current_user.id, vault_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this vault"
        )
    
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
    print("Incoming WS connection to /logs/ws")
    """
    WebSocket endpoint for real-time log and authentication event processing.

    Listens for JSON payloads representing events (e.g., unlock attempts from NFC/PIN).
    Validates, processes via services/handlers, and responds with status (e.g., "pending", "unlock").
    Each message uses a fresh DB session for atomicity.

    Args:
        websocket (WebSocket): Connected client (e.g., device sending credentials).
    """
    print("WS: Route function websocket_logs entered - before handler creation")
    import logging
    logging.info("WS: Route /logs/ws entered successfully")

    try:
        handler = LogWebSocketHandler(websocket)
        print("WS: Handler created successfully")
        logging.info("WS: LogWebSocketHandler instantiated")
        await handler.handle_connection()
    except Exception as route_err:
        print(f"WS: Exception in route function: {str(route_err)}")
        import traceback
        traceback.print_exc()
        logging.error(f"WS route exception: {route_err} - traceback: {traceback.format_exc()}")
        raise  # Re-raise to trigger 403 or close

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