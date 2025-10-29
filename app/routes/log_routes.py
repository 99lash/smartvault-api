"""
Log Routes

Handles HTTP endpoints for log operations, access analytics, and real-time log streaming.
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from app.schemas.log import LogCreate, LogRead, LogVaultSummaryRead, LogUserSummaryRead, LogVaultAttackRead, LogVaultSuspiciousRead, LogActivityReportRead, LogStatsRead
from app.schemas.LogSchemas import LogResponse
from app.schemas.Response import Response
from app.models.Log import LogEventType
from app.models.User import User, UserRole
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.services.logs.LogService import LogService
from app.services.logs.LogQueryService import LogQueryService
from app.services.logs.AccessTrackingService import AccessTrackingService
from app.services.logs.VaultAccessControllerService import VaultAccessController
from app.services.vaults.VaultService import VaultService
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.websockets.LogWebSocketHandler import LogWebSocketHandler
from app.websockets.QueryWebSocketHandler import QueryWebSocketHandler
from pydantic import BaseModel


# Constants
MAX_FAILED_ATTEMPTS_LIMIT = 1000
MAX_DAYS_LIMIT = 90
MIN_DELETE_DAYS_THRESHOLD = 7
MAX_RECENT_ACTIVITY_LIMIT = 50
DEFAULT_DEFAULT_DAYS = 7


# Request/Response Models
class ValidateAccessRequest(BaseModel):
    """Request schema for access validation."""
    vault_id: int
    details: str


class LogBulkDeleteRequest(BaseModel):
    """Request schema for bulk log deletion."""
    vault_id: Optional[str] = None
    user_id: Optional[int] = None
    event_type: Optional[str] = None
    older_than_days: Optional[int] = None
    delete_all: bool = False


class LogBulkDeleteResponse(BaseModel):
    """Response schema for bulk log deletion."""
    deleted_count: int
    vault_id: Optional[str] = None
    user_id: Optional[int] = None
    event_type: Optional[str] = None
    older_than_days: Optional[int] = None
    message: str


# Router
router = APIRouter(prefix="/logs", tags=["logs"])
logger = logging.getLogger(__name__)


# Helper Functions
def check_vault_access(user_id: int, vault_id: int, db: Session) -> None:
    """
    Check if user has access to vault, raise HTTPException if not.
    
    Args:
        user_id: User ID to check access for
        vault_id: Vault ID to check access to
        db: Database session
        
    Raises:
        HTTPException: 403 if user doesn't have access
    """
    vault_membership_repo = VaultMembershipRepository(db)
    controller = VaultAccessController(vault_membership_repo)
    if not controller.check_access(user_id, vault_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this vault"
        )


def parse_iso_date_string(date_str: str, field_name: str = "date") -> datetime:
    """
    Parse ISO format date string to datetime object.
    
    Args:
        date_str: ISO format date string
        field_name: Name of the field for error messages
        
    Returns:
        Parsed datetime object (naive, local time)
        
    Raises:
        HTTPException: 400 if date format is invalid
    """
    try:
        # Handle both formats: with and without timezone
        processed_str = date_str.replace('Z', '+00:00') if 'Z' in date_str else date_str
        parsed_date = datetime.fromisoformat(processed_str)
        
        # Return naive datetime (service layer expects local time)
        if parsed_date.tzinfo is not None:
            # Convert to naive by using local time components
            parsed_date = parsed_date.replace(tzinfo=None)
            
        return parsed_date
    except (ValueError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected ISO format (e.g., YYYY-MM-DDTHH:MM:SS), got: {date_str}. Error: {str(e)}"
        )


# Routes
@router.get("/", response_model=list[LogRead])
def list_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[LogRead]:
    """
    Retrieve all log entries from the database.
    
    This endpoint provides a complete audit trail for all events.
    
    Returns:
        List[LogRead]: Serialized log records
    """
    service = LogService(db)
    return service.get_all_logs()


@router.delete("/{log_id}", response_model=Response)
def delete_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Response:
    """
    Delete a log entry by its unique ID.
    
    Use this for administrative cleanup of audit logs (use cautiously in production).
    
    Args:
        log_id: The ID of the log to delete
        
    Returns:
        Response: Confirmation message on success
        
    Raises:
        HTTPException: 404 if the log ID does not exist
    """
    service = LogService(db)
    log = service.delete_log(log_id)
    
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Log not found"
        )
    
    return Response(success=True, detail=f"Log {log_id} deleted successfully")


@router.delete("/bulk", response_model=Response[LogBulkDeleteResponse])
def bulk_delete_logs(
    request: LogBulkDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response[LogBulkDeleteResponse]:
    """
    Bulk delete logs based on various criteria.

    **WARNING: This operation cannot be undone!**

    Request Body:
    - vault_id: Delete logs for specific vault only
    - user_id: Delete logs for specific user only
    - event_type: Delete logs of specific event type
    - older_than_days: Delete logs older than X days
    - delete_all: If true, ignore other filters and delete ALL logs (requires admin)

    **Security:** Requires admin role for dangerous operations like delete_all
    """
    # Validate admin requirement for dangerous operations
    if request.delete_all or (request.older_than_days and request.older_than_days < MIN_DELETE_DAYS_THRESHOLD):
        if current_user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this operation"
            )

    # Validate at least one filter is provided
    if not request.delete_all and not any([
        request.vault_id,
        request.user_id,
        request.event_type,
        request.older_than_days
    ]):
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
        logger.error(f"Bulk delete operation failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk delete operation failed: {str(e)}"
        )


@router.get("/vault/{vault_id}/filtered")
def get_filtered_logs(
    vault_id: int,
    prefixes: str = "DUAL,Tamper,Failure,Manual,NFC",
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """
    Get logs for a vault filtered by specific details prefixes.
    
    Args:
        vault_id: Vault ID to get logs for
        prefixes: Comma-separated list of prefixes (default: DUAL,Tamper,Failure,Manual,NFC)
        limit: Maximum number of logs to return (default: None = all matching logs)
        offset: Number of logs to skip (default: 0)
    
    Returns:
        List[dict]: Filtered and serialized logs, ordered by timestamp descending
    """
    # Check vault access
    check_vault_access(current_user.id, vault_id, db)
    
    # Get vault to retrieve device_id
    vault_service = VaultService(db)
    vault = vault_service.get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vault not found"
        )

    # Parse prefixes
    prefix_list = [p.strip() for p in prefixes.split(",") if p.strip()]

    # Query logs
    service = LogQueryService(db)
    logs = service.get_filtered_logs_by_device(vault.device_id, prefix_list, limit, offset)

    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching logs found"
        )
    
    # Serialize and return
    serialized_logs = [LogResponse(**log).model_dump() for log in logs]
    return serialized_logs


@router.websocket("/ws")
async def websocket_logs(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time log and authentication event processing.

    Listens for JSON payloads representing events (e.g., unlock attempts from NFC/PIN).
    Validates, processes via services/handlers, and responds with status (e.g., "pending", "unlock").
    Each message uses a fresh DB session for atomicity.
    """
    handler = None
    
    try:
        handler = LogWebSocketHandler(websocket)
        await handler.handle_connection()
    except WebSocketDisconnect:
        # Client disconnected normally
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        if handler:
            await handler.cleanup()


# -----------------------------
# Access Analytics Endpoints
# -----------------------------

@router.get("/access/failed-attempts", response_model=Response[List[dict]])
def get_failed_access_attempts(
    vault_id: Optional[int] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response[List[dict]]:
    """
    Get failed access attempts for security monitoring.

    Query Parameters:
    - vault_id: Filter by specific vault (optional)
    - user_id: Filter by specific user (optional)
    - start_date: Start date for filtering (ISO format string, optional)
    - end_date: End date for filtering (ISO format string, optional)
    - limit: Maximum number of results (default: 100, max: 1000)

    Returns:
        List of failed access attempts with details
    """
    # Validate access permissions
    if vault_id:
        check_vault_access(current_user.id, vault_id, db)

    # Enforce limit
    limit = min(limit, MAX_FAILED_ATTEMPTS_LIMIT)

    try:
        # Parse date strings if provided
        start_datetime = parse_iso_date_string(start_date, "start_date") if start_date else None
        end_datetime = parse_iso_date_string(end_date, "end_date") if end_date else None

        # Get failed attempts
        access_service = AccessTrackingService(db)
        failed_attempts = access_service.get_failed_access_attempts(
            vault_id=vault_id,
            user_id=user_id,
            start_date=start_datetime,
            end_date=end_datetime,
            limit=limit
        )

        return Response(
            success=True,
            data=failed_attempts,
            detail=f"Retrieved {len(failed_attempts)} failed access attempts"
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., from date parsing)
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve failed access attempts: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve failed access attempts: {str(e)}"
        )


@router.get("/access/summary", response_model=Response[dict])
def get_access_summary(
    vault_id: Optional[int] = None,
    user_id: Optional[int] = None,
    days: int = DEFAULT_DEFAULT_DAYS,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response[dict]:
    """
    Get comprehensive access summary including successful and failed attempts.

    Query Parameters:
    - vault_id: Filter by specific vault (optional)
    - user_id: Filter by specific user (optional)
    - days: Number of days to look back (default: 7, max: 90)

    Returns:
        Comprehensive access summary with trends and statistics
    """
    # Validate access permissions
    if vault_id:
        check_vault_access(current_user.id, vault_id, db)

    # Enforce date range limit for performance
    days = min(days, MAX_DAYS_LIMIT)

    try:
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get access summary
        access_service = AccessTrackingService(db)
        summary = access_service.get_access_summary(
            vault_id=vault_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            days=days
        )

        return Response(
            success=True,
            data=summary,
            detail=f"Access summary for the last {days} days"
        )

    except Exception as e:
        logger.error(f"Failed to retrieve access summary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve access summary: {str(e)}"
        )


@router.get("/access/recent-activity", response_model=Response[List[dict]])
def get_recent_activity(
    vault_id: Optional[int] = None,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response[List[dict]]:
    """
    Get recent activity for the activity feed, including both successful unlocks and failed attempts.

    Query Parameters:
    - vault_id: Filter by specific vault (optional)
    - limit: Maximum number of activities to return (default: 10, max: 50)

    Returns:
        List of recent activities with details for the activity feed
    """
    # Validate access permissions
    if vault_id:
        check_vault_access(current_user.id, vault_id, db)

    # Enforce limit
    limit = min(limit, MAX_RECENT_ACTIVITY_LIMIT)

    try:
        # Get recent activity
        access_service = AccessTrackingService(db)
        activities = access_service.get_recent_activity(
            vault_id=vault_id,
            limit=limit
        )

        return Response(
            success=True,
            data=activities,
            detail=f"Retrieved {len(activities)} recent activities"
        )

    except Exception as e:
        logger.error(f"Failed to retrieve recent activity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent activity: {str(e)}"
        )


@router.websocket("/ws/query")
async def websocket_query_logs(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for querying filtered logs.

    On connection, expects a JSON payload with vault_id and prefixes.
    Responds with the filtered logs as a JSON array.
    Handles errors and disconnections gracefully.
    """
    handler = None

    try:
        handler = QueryWebSocketHandler(websocket)
        await handler.handle_connection()
    except WebSocketDisconnect:
        # Client disconnected normally
        pass
    except Exception as e:
        logger.error(f"WebSocket query error: {str(e)}", exc_info=True)
    finally:
        if handler:
            await handler.cleanup()
