from sqlalchemy.orm import Session
from app.models.Vault import Vault, VaultStatus
from app.repositories.Repository import Repository  # BaseRepository

class VaultRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, Vault)

    # Get a vault by name
    def get_by_name(self, name: str):
        return self.db.query(self.model).filter(self.model.name == name).first()

    # Get a vault by device_id
    def get_by_device_id(self, device_id: str):
        return self.db.query(self.model).filter(self.model.device_id == device_id).first()

    # Update vault status
    def update_status(self, vault_id: int, status: VaultStatus):
        """Update vault status by vault id"""
        return self.update(vault_id, status=status)

    # Optional: restore a soft-deleted vault
    def restore(self, vault_id: int):
        """Restore a soft-deleted vault by vault id"""
        if not hasattr(self.model, "deleted_at"):
            return None
        vault = self.db.query(self.model).filter(self.model.id == vault_id, self.model.deleted_at != None).first()
        if vault:
            vault.deleted_at = None
            self.db.commit()
            self.db.refresh(vault)
        return vault

    # Optional: get all deleted vaults
    def get_deleted(self):
        """Get all soft-deleted vaults"""
        if not hasattr(self.model, "deleted_at"):
            return []
        return self.db.query(self.model).filter(self.model.deleted_at != None).all()

    # Hard delete a vault (permanent removal)
    def hard_delete(self, vault_id: int) -> Vault | None:
        """
        Permanently delete a vault from the database.
        WARNING: This action cannot be undone!
        """
        vault = self.db.query(self.model).filter(self.model.id == vault_id).first()
        if vault:
            self.db.delete(vault)
            self.db.commit()
        return vault
