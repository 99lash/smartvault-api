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
from app.models.User import User, UserRole
from app.schemas.Response import Response
from app.core.database import SessionLocal
from pydantic import BaseModel
from app.services.vaults.VaultService import VaultService
from app.services.users.UserService import UserService
from app.services.Logs.VaultAccessControllerService import VaultAccessController
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
# from app.models.Log import Log;

class ValidateAccessRequest(BaseModel):
    vault_id: int
    details: str

class LogBulkDeleteRequest(BaseModel):
    """Request schema for bulk log deletion"""
    vault_id: Optional[str] = None
    user_id: Optional[int] = None
    event_type: Optional[str] = None
    older_than_days: Optional[int] = None
    delete_all: bool = False

class LogBulkDeleteResponse(BaseModel):
    """Response schema for bulk log deletion"""
    deleted_count: int
    vault_id: Optional[str] = None
    user_id: Optional[int] = None
    event_type: Optional[str] = None
    older_than_days: Optional[int] = None
    message: str

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

# -----------------------------
# Bulk delete logs
# -----------------------------
@router.delete("/bulk", response_model=Response[LogBulkDeleteResponse])
def bulk_delete_logs(
    request: LogBulkDeleteRequest,
    current_user: User = Depends(UserService.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bulk delete logs based on various criteria.

    **WARNING: This operation cannot be undone!**

    Query Parameters (all optional):
    - vault_id: Delete logs for specific vault only
    - user_id: Delete logs for specific user only
    - event_type: Delete logs of specific event type (unlock, failed_attempt, tamper, etc.)
    - older_than_days: Delete logs older than X days
    - delete_all: If true, ignore other filters and delete ALL logs (requires admin)

    **Security:** Requires admin role for dangerous operations like delete_all
    """

    # Check if user is admin for dangerous operations
    if request.delete_all or (request.older_than_days and request.older_than_days < 7):
        if current_user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this operation"
            )

    # Validate that at least one filter is provided (unless admin deleting all)
    if not request.delete_all and not any([request.vault_id, request.user_id, request.event_type, request.older_than_days]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one filter must be provided (or use delete_all for admin)"
        )

    try:
        service = LogService(db)
        deleted_count = service.bulk_delete_logs(
            vault_id=request.vault_id,
            user_id=request.user_id,
            event_type=request.event_type,
            older_than_days=request.older_than_days,
            delete_all=request.delete_all
        )

        response_data = LogBulkDeleteResponse(
            deleted_count=deleted_count,
            vault_id=request.vault_id,
            user_id=request.user_id,
            event_type=request.event_type,
            older_than_days=request.older_than_days,
            message=f"Successfully deleted {deleted_count} log entries"
        )

        return Response(success=True, data=response_data, detail=response_data.message)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk delete operation failed: {str(e)}"
        )

@router.get("/vault/{vault_id}/filtered")
def get_filtered_logs(
    vault_id: int,
    prefixes: str = "DUAL,Tamper,Failure,Manual",
    current_user = Depends(UserService.get_current_user),
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
    vault_membership_repo = VaultMembershipRepository(db)
    controller = VaultAccessController(vault_membership_repo)
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
# TESTING ENDPOINT POST /test 
# -----------------------------
#
# # @router.post("/test", status_code=status.HTTP_201_CREATED)
# def create_log_test(payload: LogCreate, db: Session = Depends(get_db)):
#     try:
#         log = Log(
#             device_id=payload.device_id,
#             user_id=payload.user_id,
#             event_type=payload.event_type,
#             details=payload.details
#         )
#         db.add(log)
#         db.commit()
#         db.refresh(log)
#         return {
#             "success": True,
#             "data": log,
#             "message": "Log inserted successfully."
#         }

#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to insert log: {e}"
#         )

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