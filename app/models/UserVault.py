from sqlmodel import Field, SQLModel, Relationship
from typing import Optional
from .Model import Model

class UserVault(Model, table=True):

    user_id: int = Field(foreign_key="users.id", nullable=False)
    vault_id: int = Field(foreign_key="vaults.id", nullable=False)
    nfc_id: Optional[str] = Field(default=None, nullable=True)
    pin_code: Optional[str] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True, nullable=False)

    user = Relationship(back_populates="user_vaults")
    vault = Relationship(back_populates="user_vaults")
