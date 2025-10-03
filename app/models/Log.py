from sqlmodel import Field, SQLModel, Relationship
from typing import Optional, TYPE_CHECKING
import enum
from datetime import datetime
from .Model import Model  # Base model with id

if TYPE_CHECKING:
    from .Vault import Vault
    from .User import User 

# ENUM for log event types
class LogEventType(str, enum.Enum):
    unlock = "unlock"
    lock = "lock"
    failed_attempt = "failed_attempt"
    tamper = "tamper"
    alarm = "alarm"
    disconnected = "disconnected"
    need_other_factor = "need_other_factor"
    access_granted = "access_granted"
    connected = "connected"
    

# Log model
class Log(Model, table=True):
    __tablename__ = "logs"

    vault_id: int = Field(foreign_key="vaults.id", nullable=False)
    user_id: Optional[int] = Field(foreign_key="users.id", default=None)  # nullable if unknown intruder
    event_type: LogEventType = Field(nullable=False)
    # Use created_at from base Model instead of separate timestamp field
    details: Optional[str] = Field(default=None, nullable=True)  # JSON or text info

    # Optional relationships for ORM
    vault: Optional["Vault"] = Relationship(back_populates="logs")
    user: Optional["User"] = Relationship(back_populates="logs")
