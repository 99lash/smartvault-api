from sqlalchemy.orm import Session
from typing import List, Optional
from app.models.VaultMembership import VaultMembership, MembershipRole
from .Repository import Repository
from app.models.User import User
from app.models.Vault import Vault

class VaultMembershipRepository(Repository):
    """
    Repository for VaultMembership persistence.
    Handles direct database queries (no business logic).
    """

    def __init__(self, db: Session):
        super().__init__(db, VaultMembership)

    def get_by_user_and_vault(self, user_id: int, vault_id: int) -> Optional[VaultMembership]:
        return (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id, self.model.vault_id == vault_id)
            .first()
        )

    def get_user_memberships(self, user_id: int) -> List[VaultMembership]:
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()

    def get_vault_memberships(self, vault_id: int) -> List[VaultMembership]:
        return self.db.query(self.model).filter(self.model.vault_id == vault_id).all()

    def get_memberships_by_role(self, vault_id: int, role: MembershipRole) -> List[VaultMembership]:
        return (
            self.db.query(self.model)
            .filter(self.model.vault_id == vault_id, self.model.role == role)
            .all()
        )

    def get_vaults_for_user(self, user_id: int) -> List[Vault]:
        return (
            self.db.query(Vault)
            .join(self.model, Vault.id == self.model.vault_id)
            .filter(self.model.user_id == user_id)
            .all()
        )

    def get_users_for_vault(self, vault_id: int) -> List[User]:
        return (
            self.db.query(User)
            .join(self.model, User.id == self.model.user_id)
            .filter(self.model.vault_id == vault_id, User.deleted_at == None)
            .all()
        )

    def add(self, membership: VaultMembership) -> VaultMembership:
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def delete(self, membership: VaultMembership) -> None:
        self.db.delete(membership)
        self.db.commit()
