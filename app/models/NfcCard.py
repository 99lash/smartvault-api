from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from datetime import datetime
from .Model import Model
from .User import User

# Type-only imports to avoid circular dependency issues
if TYPE_CHECKING:
    from .Vault import Vault

class NfcCard(Model, table=True):
    __tablename__ = "nfc_cards"

    uid: str = Field(nullable=False, unique=True, index=True, description="Unique NFC card identifier")
    name: Optional[str] = Field(default=None, nullable=True, description="User-defined name for the card")
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", description="Owner of the NFC card")
    vault_id: int = Field(foreign_key="vaults.id", nullable=False, index=True, description="Vault this NFC card belongs to")
    
    # relationships
    user: Optional["User"] = Relationship(back_populates="nfc_cards")
    vault: Optional["Vault"] = Relationship(back_populates="nfc_cards")
