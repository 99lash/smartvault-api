from sqlmodel import Field, Relationship
import enum
from typing import Optional
from datetime import datetime, timezone
from .Model import Model
from .User import User
from .Vault import Vault

class LogEventType(str, enum.Enum):
    unlock = "unlock"
    failed_attempt = "failed_attempt"
    tamper = "tamper"
    alarm = "alarm"

class Log(Model, table=True):
    __tablename__ = "logs"

    vault_id: int = Field(foreign_key="vaults.id", nullable=False)
    user_id: Optional[int] = Field(foreign_key="users.id", nullable=True)
    event_type: LogEventType = Field(nullable=False)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    details: Optional[str] = Field(default=None, sa_column_kwargs={"type": "JSON"})

    vault: Vault = Relationship(back_populates="logs")
    user: Optional[User] = Relationship(back_populates="logs")
