from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional, List, TYPE_CHECKING
from .Model import Model  # base model with id

if TYPE_CHECKING:
    from .NonAdminUser import NonAdminUser


class KeypadPins(Model, table=True):
    __tablename__ = "keypad_pins"

    # Remove unique=True from pin_code, make it indexed only
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    pin_code: str = Field(index=True, nullable=False)

    non_admin_users: Optional[List["NonAdminUser"]] = Relationship(back_populates="keypad_pin")

    # Add composite unique constraint: same user cannot have duplicate pins
    __table_args__ = (
        UniqueConstraint("user_id", "pin_code", name="uq_user_pin"),
    )
