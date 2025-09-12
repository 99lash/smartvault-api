from sqlalchemy.orm import Session
from app.repositories.VaultRepository import VaultRepository
from app.models.Vault import Vault, VaultStatus

# -----------------------------
# Service layer for Vault logic
# -----------------------------
# Encapsulates business logic related to vaults:
# - using DB operations through VaultRepository
# - status updates
class VaultService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = VaultRepository(db)

    # Create a new vault
    def create_vault(self, name: str, location: str | None = None, status: VaultStatus = VaultStatus.locked) -> Vault:
        return self.repo.create(name=name, location=location, status=status)

    # Fetch a vault by ID
    def get_vault_by_id(self, vault_id: int) -> Vault | None:
        return self.repo.get_by_id(vault_id)

    # Fetch a vault by name
    def get_vault_by_name(self, name: str) -> Vault | None:
        return self.repo.get_by_name(name)

    # List all vaults
    def list_vaults(self) -> list[Vault]:
        return self.repo.get_all()

    # Delete a vault by ID
    def delete_vault(self, vault_id: int) -> Vault | None:
        return self.repo.delete(vault_id)

    # Update a vault's status
    def update_vault_status(self, vault_id: int, status: VaultStatus) -> Vault | None:
        return self.repo.update(vault_id, status=status)

    # Optional: restore a soft-deleted vault
    def restore_vault(self, vault_id: int) -> Vault | None:
        return self.repo.restore(vault_id)
