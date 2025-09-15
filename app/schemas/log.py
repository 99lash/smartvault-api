from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, time
from app.models.Log import LogEventType
# ----------------------------
# Log HTTP Request Schemas
# ----------------------------
class LogCreate(SQLModel, table=False):
    vault_id: int = Field(..., ge=1, description="The ID of the vault associated with the log")
    event_type: LogEventType = Field(..., description="The type of log event")
    user_id: Optional[int] = Field(None, ge=1, description="The ID of the user who triggered the event (optional)")
    details: Optional[str] = Field(None, max_length=1000, description="Additional details about the event")

# ----------------------------
# Log HTTP Response Schemas
# ----------------------------
class LogRead(SQLModel, table=False):
    id: int
    vault_id: int
    user_id: Optional[int] = None
    event_type: LogEventType
    timestamp: datetime
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# ---------------------------------------------
class LogVaultSummaryRead(SQLModel, table=False):
    total_events: int
    unlock_count: int
    failed_attempts: int
    security_alerts: int
    last_activity: Optional[datetime] = None

    class Config:
        from_attributes = True

# ---------------------------------------------
class VaultBreakdown(SQLModel, table=False):
    unlocks: int
    failed_attempts: int

class LogUserSummaryRead(SQLModel, table=False):
    total_activities: int
    vaults_accessed: int
    vault_breakdown: dict[int, VaultBreakdown]
    period_hours: int

    class Config:
        from_attributes = True

# ---------------------------------------------
class LogVaultAttackRead(SQLModel, table=False):
    detail: bool

    class Config:
        from_attributes = True

# ---------------------------------------------
class EventBreakdown(SQLModel, table=False):
    tamper: int
    alarm: int
    unlock: int

class VaultsIssuesBreakdown(SQLModel, table=False):
    failed_attempts: int
    tamper_events: int
    alarms: int
    total_events: int

class LogVaultSuspiciousRead(SQLModel, table=False):
    report_period_hours: int
    total_security_events: int
    event_type_breakdown: EventBreakdown
    vaults_with_issues: dict[int , VaultsIssuesBreakdown]
    high_risk_vaults: list[int]
  
    class Config:
        from_attributes = True

# ---------------------------------------------
class LogPeriod(SQLModel, table=False):
    start: datetime
    end: datetime
    vault_id: Optional[int] = None

class LogActivityReportRead(SQLModel, table=False):
    period: LogPeriod
    total_events: int
    event_breakdown: EventBreakdown
    daily_activity: dict[datetime, int]
    busiest_hours: dict[int, int]

    class Config:
        from_attributes = True

# ---------------------------------------------
class LogStatsRead(SQLModel, table=False):
    total_logs: int
    oldest_log: datetime
    newest_log: datetime
    storage_period_days: int

    class Config:
        from_attributes = True