from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional, Dict
from datetime import datetime, timedelta
from app.schemas.LogCreate import LogCreate
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.Logs.LogService import LogService
from app.models.Log import LogEventType
from app.core.database import SessionLocal
from pydantic import BaseModel

class ValidateAccessRequest(BaseModel):
    vault_id: int
    details: str

# -----------------------------
# router for Log endpoints
# -----------------------------
# Handles HTTP/WebSocket requests for log management and real-time authentication events.
# - HTTP: CRUD operations for logs (list, delete)
# - WebSocket: Real-time processing of unlock attempts, tamper detection, etc.
# Delegates business logic to LogService for separation of concerns (SOC).
router = APIRouter(prefix="/logs", tags=["logs"])

# -----------------------------
# HTTP Endpoints for Log Management
# -----------------------------
# Basic CRUD operations for retrieving and managing logs.

# -----------------------------
# Retrieve all log entries
# -----------------------------
@router.get("/")
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
@router.delete("/{log_id}")
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
        raise HTTPException(status_code=404, detail="Log not found")
    return {"message": f"Log {log_id} deleted successfully"}
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
    Validates, processes via LogService, and responds with status (e.g., "pending", "unlock").
    Each message uses a fresh DB session for atomicity.
    
    Args:
        websocket (WebSocket): Connected client (e.g., device sending credentials).
    
    Handles:
        - Connection acceptance and message loop.
        - Event dispatching based on payload.event_type.
        - Graceful error handling and disconnection.
    """
    await websocket.accept()  # Accept the WebSocket connection
    try:
        while True:  # Main message processing loop
            # Receive raw text message from client
            raw_data = await websocket.receive_text()
            try:
                # Parse and validate incoming payload against Pydantic schema
                payload = LogCreate.model_validate_json(raw_data)

                # Create a new DB session for this message to ensure isolation
                with SessionLocal() as db:
                    service = LogService(db)  # Instantiate service with session
                    
                    # Dispatch based on event type
                    if payload.event_type == LogEventType.unlock and payload.details:
                        # Handle authentication/unlock requests (MFA support)
                        await _handle_unlock_request(websocket, payload, service)
                    
                    elif payload.event_type == LogEventType.failed_attempt and payload.details:
                        # Log explicit failed attempts (e.g., from client-side validation)
                        new_log = service.log_failed_unlock_attempt(
                            vault_id=payload.vault_id,
                            user_id=None,  # Anonymous for failed attempts
                            reason=payload.details
                        )
                        service.clear_sessions_for_vault(payload.vault_id)
                        await websocket.send_json({"status": "ok", "event_type": "failed_attempt"})
                    
                    elif payload.event_type == LogEventType.tamper and payload.details:
                        # Log tamper or security events (e.g., sensor triggers)
                        new_log = service.log_tamper_detection(
                            vault_id=payload.vault_id,
                            sensor_data=payload.details
                        )
                        service.clear_sessions_for_vault(payload.vault_id)
                        await websocket.send_json({"status": "ok", "event_type": "tamper"})
                    
                    else:
                        # Generic log creation for unsupported or custom events
                        new_log = service.create_log(
                            vault_id=payload.vault_id,
                            event_type=payload.event_type,
                            user_id=None,  # Default to anonymous
                            details=payload.details,
                        )
                        if new_log:
                            # Confirm successful logging
                            await websocket.send_json({"status": "ok", "event_type": new_log.event_type.value})
                        else:
                            # Invalid event - reject without logging
                            await websocket.send_json({"status": "error", "message": "Invalid event_type or details"})

            except Exception as e:
                # Catch validation/parsing errors and respond with error status
                await websocket.send_json({"status": "error", "error": str(e)})
                
    except WebSocketDisconnect:
        # Handle client disconnection gracefully
        print("WebSocket disconnected: /logs/ws")


async def _handle_unlock_request(websocket: WebSocket, payload: LogCreate, service: LogService):
    """
    Handle unlock authentication requests via progressive MFA.
    
    First checks for pending sessions (second factor); otherwise, initiates new auth.
    Uses service for validation/logging; maps results to client-friendly JSON responses.
    
    Args:
        websocket (WebSocket): Client connection for sending responses.
        payload (LogCreate): The unlock event payload with details (NFC/PIN).
        service (LogService): Initialized service for auth logic.
    
    Flow:
        1. Clean expired sessions.
        2. Check for second factor (if session exists).
        3. If first factor, validate and respond with status (unlock/pending/etc.).
    """
    log_entry, status = service.validate_progressive_access(
        vault_id=payload.vault_id,
        details=payload.details
    )
    
    # Map authentication statuses to standardized JSON responses for client
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
        
        # Customize message for dual unlock
        if status == 'unlock' and log_entry and 'DUAL' in log_entry.details:
            resp["message"] = "Dual authentication successful"
        
        # Customize message for repeated factor
        if status == 'invalid_credentials' and log_entry and "Same factor repeated" in log_entry.details:
            resp["message"] = "Invalid second factor or same factor repeated"
        
        if status == 'invalid_credentials':
            service.clear_sessions_for_vault(payload.vault_id)
        
        await websocket.send_json(resp)
    else:
        # Fallback for unexpected statuses (defensive programming)
        await websocket.send_json({
            "status": "error",
            "message": f"Unknown status: {status}"
        })