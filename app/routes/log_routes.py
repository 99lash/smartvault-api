from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from typing import Optional
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.LogService import LogService
from datetime import datetime
from app.models.Log import LogEventType
from app.schemas.log import LogCreate, LogRead, LogVaultSummaryRead, LogUserSummaryRead, LogVaultAttackRead, LogVaultSuspiciousRead, LogActivityReportRead, LogStatsRead
from app.schemas.Response import Response
from app.services.VaultService import VaultService
from app.services.UserService import UserService
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
@router.get("/", response_model=list[LogRead])
def list_logs(db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_all_logs()

# -----------------------------
# Get log by ID
# -----------------------------
@router.get("/{log_id}", response_model=LogRead)
def get_log(log_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    log = service.get_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    return log

# -----------------------------
# Delete a log
# -----------------------------
@router.delete("/{log_id}", response_model=Response)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    log = service.delete_log(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log not found")
    return Response(success=True, detail=f"Log {log_id} deleted successfully")

# -----------------------------
# Vault logs & summary
# -----------------------------
@router.get("/vault/{vault_id}", response_model=list[LogRead])
def get_vault_logs(vault_id: int, db: Session = Depends(get_db)):
    vault = VaultService(db).get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    service = LogService(db)
    return service.get_vault_logs(vault_id)

@router.get("/vault/{vault_id}/summary", response_model=LogVaultSummaryRead)
def get_vault_summary(vault_id: int, hours: int = 24, db: Session = Depends(get_db)):
    vault = VaultService(db).get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    service = LogService(db)
    return service.get_vault_activity_summary(vault_id, hours)

# -----------------------------
# User logs & summary
# -----------------------------
@router.get("/user/{user_id}", response_model=list[LogRead])
def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    user = UserService(db).get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    service = LogService(db)
    return service.get_user_logs(user_id)

@router.get("/user/{user_id}/summary", response_model=LogUserSummaryRead)
def get_user_summary(user_id: int, hours: int = 24, db: Session = Depends(get_db)):
    user = UserService(db).get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    service = LogService(db)
    return service.get_user_activity_summary(user_id, hours)

# -----------------------------
# Security checks
# -----------------------------
@router.get("/vault/{vault_id}/alerts", response_model=list[LogRead])
def check_vault_alerts(vault_id: int, hours: int = 1, db: Session = Depends(get_db)):
    vault = VaultService(db).get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    service = LogService(db)
    return service.check_security_alerts(vault_id, hours)

@router.get("/vault/{vault_id}/attack", response_model=LogVaultAttackRead)
def is_vault_under_attack(vault_id: int, threshold: int = 5, minutes: int = 30, db: Session = Depends(get_db)):
    vault = VaultService(db).get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    service = LogService(db)
    return {"under_attack": service.is_vault_under_attack(vault_id, threshold, minutes)}

@router.get("/vaults/suspicious", response_model=LogVaultSuspiciousRead) # This has a conflict path with the `/logs/{log_id}`, so I changed it to `/logs/vaults/suspicious`
def suspicious_report(hours: int = 24, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_suspicious_activity_report(hours)

# -----------------------------
# Activity reports
# -----------------------------
@router.get("/vaults/report", response_model=LogActivityReportRead)
def activity_report(start: datetime, end: datetime, vault_id: int | None = None, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_activity_report(start, end, vault_id)

@router.get("/vaults/paginated", response_model=list[LogRead])
def paginated_logs(page: int = 1, per_page: int = 20, vault_id: int | None = None,
                   event_type: LogEventType | None = None, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_paginated_logs(page, per_page, vault_id, event_type)

# -----------------------------
# Maintenance
# -----------------------------
@router.delete("/vaults/cleanup", response_model=Response)
def cleanup_old_logs(retention_days: int = 90, db: Session = Depends(get_db)):
    service = LogService(db)
    deleted = service.cleanup_old_logs(retention_days)
    return Response(success=True, data=None, detail=f"Deleted {deleted} old logs")

@router.get("/vaults/stats", response_model=LogStatsRead)
def storage_stats(db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_storage_stats()

# -----------------------------
# Test validation endpoint (HTTP for easy funciton testing via /docs)
# -----------------------------
@router.post("/validate-access")
def validate_access(request: ValidateAccessRequest, db: Session = Depends(get_db)):
    service = LogService(db)
    log = service.validate_access_and_create_log(vault_id=request.vault_id, details=request.details)
    if log:
        return {
            "success": True,
            "event_type": log.event_type.value,
            "user_id": log.user_id,
            "details": log.details
        }
    else:
        return {"success": False, "message": "No log created - invalid details or no access"}

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
                # Validate incoming message against existing schema
                payload = LogCreate.model_validate_json(raw_data)

                with SessionLocal() as db:
                    service = LogService(db)
                    if payload.event_type == LogEventType.unlock and payload.details:
                        # For unlock attempts, validate access via NFC or PIN
                        new_log = service.validate_access_and_create_log(
                            vault_id=payload.vault_id,
                            details=payload.details
                        )
                        if new_log:
                            event_type_str = new_log.event_type.value
                            status = "ok" if event_type_str == "unlock" else "no_access"
                            await websocket.send_json({"status": status, "event_type": event_type_str})
                        else:
                            # No user found, log as failed attempt
                            new_log = service.log_failed_unlock_attempt(
                                vault_id=payload.vault_id,
                                user_id=None,
                                reason=payload.details or "unknown"
                            )
                            await websocket.send_json({"status": "no_access", "event_type": "failed_attempt"})
                    elif payload.event_type == LogEventType.failed_attempt and payload.details:
                        # Direct failed attempt log
                        new_log = service.log_failed_unlock_attempt(
                            vault_id=payload.vault_id,
                            user_id=None,
                            reason=payload.details
                        )
                        await websocket.send_json({"status": "ok", "event_type": "failed_attempt"})
                    elif payload.event_type == LogEventType.tamper and payload.details:
                        # Direct tamper detection log
                        new_log = service.log_tamper_detection(
                            vault_id=payload.vault_id,
                            sensor_data=payload.details
                        )
                        await websocket.send_json({"status": "ok", "event_type": "tamper"})
                    else:
                        # For other event types, use direct create
                        new_log = service.create_log(
                            vault_id=payload.vault_id,
                            event_type=payload.event_type,
                            user_id=None,  # Default for non-user events
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
