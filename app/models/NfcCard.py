from sqlmodel import SQLModel, Field, Relationship
from typing import Optional
from datetime import datetime
from .Model import Model
from .User import User

class NfcCard(Model, table=True):
    __tablename__ = "nfc_cards"

    uid: str = Field(nullable=False, unique=True, index=True, description="Unique NFC card identifier")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", description="Owner of the NFC card")
    # relationships (optional, if you have User model)
    user: Optional["User"] = Relationship(back_populates="nfc_cards")
