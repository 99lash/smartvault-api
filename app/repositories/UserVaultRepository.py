from sqlalchemy.orm import Session
from app.models.UserVault import UserVault
from app.models.User import User
from app.models.Vault import Vault
from app.repositories.Repository import Repository

class UserVaultRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, UserVault)

    def get_by_user_and_vault(self, user_id: int, vault_id: int):
        return (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id, self.model.vault_id == vault_id)
            .first()
        )

    def get_vaults_for_user(self, user_id: int):
        return (
            self.db.query(Vault)
            .join(self.model)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_users_for_vault(self, vault_id: int):
        return (
            self.db.query(User)
            .join(self.model)
            .filter(self.model.vault_id == vault_id)
            .all()
        )

    def has_access(self, user_id: int, vault_id: int):
        return self.get_by_user_and_vault(user_id, vault_id) is not None