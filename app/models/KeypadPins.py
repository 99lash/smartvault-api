from sqlmodel import Field, SQLModel
from typing import Optional
from .Model import Model  # base model with id


class KeypadPins(Model, table=True):
    __tablename__ = "keypad_pins"

    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    pin_code: str = Field(index=True, unique=True, nullable=False)  
