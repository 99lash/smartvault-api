from sqlmodel import Field, SQLModel, Relationship, UniqueConstraint
from typing import Optional
from .Model import Model  # base model with id


class KeypadPins(Model, table=True):
    __tablename__ = "keypad_pins"

    # Remove unique=True from pin_code, make it indexed only
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    vault_id: int = Field(foreign_key="vaults.id", nullable=False, index=True)
    pin_code: str = Field(index=True, nullable=False)

    # Add composite unique constraint: same user cannot have duplicate pins within same vault
    __table_args__ = (
        UniqueConstraint("user_id", "vault_id", "pin_code", name="uq_user_vault_pin"),
    )
