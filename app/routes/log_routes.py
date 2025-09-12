from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.schemas.LogCreate import LogCreate
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.LogService import LogService
from datetime import datetime
from app.models.Log import LogEventType

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
# Get log by ID
# -----------------------------
@router.get("/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    log = service.get_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")
    return log

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
# Vault logs & summary
# -----------------------------
@router.get("/vault/{vault_id}")
def get_vault_logs(vault_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_vault_logs(vault_id)

@router.get("/vault/{vault_id}/summary")
def get_vault_summary(vault_id: int, hours: int = 24, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_vault_activity_summary(vault_id, hours)

# -----------------------------
# User logs & summary
# -----------------------------
@router.get("/user/{user_id}")
def get_user_logs(user_id: int, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_user_logs(user_id)

@router.get("/user/{user_id}/summary")
def get_user_summary(user_id: int, hours: int = 24, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_user_activity_summary(user_id, hours)

# -----------------------------
# Security checks
# -----------------------------
@router.get("/vault/{vault_id}/alerts")
def check_vault_alerts(vault_id: int, hours: int = 1, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.check_security_alerts(vault_id, hours)

@router.get("/vault/{vault_id}/attack")
def is_vault_under_attack(vault_id: int, threshold: int = 5, minutes: int = 30, db: Session = Depends(get_db)):
    service = LogService(db)
    return {"under_attack": service.is_vault_under_attack(vault_id, threshold, minutes)}

@router.get("/suspicious")
def suspicious_report(hours: int = 24, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_suspicious_activity_report(hours)

# -----------------------------
# Activity reports
# -----------------------------
@router.get("/report")
def activity_report(start: datetime, end: datetime, vault_id: int | None = None, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_activity_report(start, end, vault_id)

@router.get("/paginated")
def paginated_logs(page: int = 1, per_page: int = 20, vault_id: int | None = None,
                   event_type: LogEventType | None = None, db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_paginated_logs(page, per_page, vault_id, event_type)

# -----------------------------
# Maintenance
# -----------------------------
@router.delete("/cleanup")
def cleanup_old_logs(retention_days: int = 90, db: Session = Depends(get_db)):
    service = LogService(db)
    deleted = service.cleanup_old_logs(retention_days)
    return {"message": f"Deleted {deleted} old logs"}

@router.get("/stats")
def storage_stats(db: Session = Depends(get_db)):
    service = LogService(db)
    return service.get_storage_stats()

@router.post("/")
def create_log(
    log_data: LogCreate,
    db: Session = Depends(get_db)
):
    from app.schemas.LogCreate import LogCreate
    service = LogService(db)
    new_log = service.create_log(
        vault_id=log_data.vault_id,
        event_type=log_data.event_type,
        user_id=log_data.user_id,
        details=log_data.details
    )
    return new_log

