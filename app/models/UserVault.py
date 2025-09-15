from sqlmodel import Field, Relationship
from typing import Optional, TYPE_CHECKING
from .Model import Model

if TYPE_CHECKING:
    from .User import User
    from .Vault import Vault

class UserVault(Model, table=True):
    __tablename__ = "user_vaults"

    user_id: int = Field(foreign_key="users.id")
    vault_id: int = Field(foreign_key="vaults.id")

    user: Optional["User"] = Relationship(back_populates="user_vaults")
    vault: Optional["Vault"] = Relationship(back_populates="user_vaults")