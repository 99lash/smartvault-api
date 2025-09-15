from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional, Dict
from datetime import datetime, timedelta
from app.schemas.LogCreate import LogCreate
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.LogService import LogService
from app.models.Log import LogEventType
from app.core.database import SessionLocal
from pydantic import BaseModel

class ValidateAccessRequest(BaseModel):
    vault_id: int
    details: str

# -----------------------------
# FastAPI router for Log endpoints
# -----------------------------
# Handles HTTP requests related to logs:
# - list, fetch, delete
# - summaries (vault & user)
# - security alerts
# - reports
router = APIRouter(prefix="/logs", tags=["logs"])

# -----------------------------
# Get all logs
# -----------------------------
@router.get("/")
def list_logs(db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_all_logs()
# -----------------------------
# Delete a log
# -----------------------------
@router.delete("/{log_id}")
def delete_log(log_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    log = service.delete_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return {"message": f"Log {log_id} deleted successfully"}
# -----------------------------
# WEBSOCKET ENDPOINTS
# -----------------------------

@router.websocket("/ws")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                payload = LogCreate.model_validate_json(raw_data)

                with SessionLocal() as db:
                    service = LogService(db)
                    
                    if payload.event_type == LogEventType.unlock and payload.details:
                        # Clean up expired sessions first
                        service.cleanup_expired_sessions()
                        
                        # Check if this might be a second factor for an existing session
                        # Parse the credential to get user_id
                        temp_user_id = service.extract_user_id_from_details(payload.details)
                        
                        if temp_user_id:
                            session_key = service.get_session_key(payload.vault_id, temp_user_id)
                            
                            # If there's an active session, try second factor authentication
                            if session_key in LogService.auth_sessions:
                                log_entry, status = service.handle_second_factor(
                                    vault_id=payload.vault_id,
                                    details=payload.details
                                )
                                
                                if status == 'unlock':
                                    await websocket.send_json({
                                        "status": "ok", 
                                        "event_type": "unlock",
                                        "user_id": log_entry.user_id if log_entry else None,
                                        "message": "Dual authentication successful"
                                    })
                                    continue
                                elif status == 'invalid_credentials':
                                    await websocket.send_json({
                                        "status": "invalid_credentials", 
                                        "event_type": "failed_attempt",
                                        "message": "Invalid second factor or same factor repeated"
                                    })
                                    continue
                        
                        # If not second factor, proceed with normal progressive auth
                        log_entry, status = service.validate_progressive_access(
                            vault_id=payload.vault_id,
                            details=payload.details
                        )
                        
                        if status == 'unlock':
                            await websocket.send_json({
                                "status": "ok", 
                                "event_type": "unlock",
                                "user_id": log_entry.user_id if log_entry else None,
                                "message": "Access granted"
                            })
                        elif status == 'pending':
                            await websocket.send_json({
                                "status": "pending", 
                                "event_type": "pending",
                                "user_id": log_entry.user_id if log_entry else None,
                                "message": "First factor accepted, provide second factor"
                            })
                        elif status == 'no_access':
                            await websocket.send_json({
                                "status": "no_access", 
                                "event_type": "tamper",
                                "user_id": log_entry.user_id if log_entry else None,
                                "message": "Access denied - insufficient permissions"
                            })
                        else:  # invalid_credentials
                            await websocket.send_json({
                                "status": "invalid_credentials", 
                                "event_type": "failed_attempt",
                                "message": "Invalid credentials"
                            })
                    
                    elif payload.event_type == LogEventType.failed_attempt and payload.details:
                        new_log = service.log_failed_unlock_attempt(
                            vault_id=payload.vault_id,
                            user_id=None,
                            reason=payload.details
                        )
                        await websocket.send_json({"status": "ok", "event_type": "failed_attempt"})
                    
                    elif payload.event_type == LogEventType.tamper and payload.details:
                        new_log = service.log_tamper_detection(
                            vault_id=payload.vault_id,
                            sensor_data=payload.details
                        )
                        await websocket.send_json({"status": "ok", "event_type": "tamper"})
                    
                    else:
                        new_log = service.create_log(
                            vault_id=payload.vault_id,
                            event_type=payload.event_type,
                            user_id=None,
                            details=payload.details,
                        )
                        if new_log:
                            await websocket.send_json({"status": "ok", "event_type": new_log.event_type.value})
                        else:
                            await websocket.send_json({"status": "error", "message": "Invalid event_type or details"})

            except Exception as e:
                await websocket.send_json({"status": "error", "error": str(e)})
                
    except WebSocketDisconnect:
        print("WebSocket disconnected: /logs/ws")