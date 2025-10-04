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

    def create_vault(self, device_id: str, name: str, location: str | None = None, status: VaultStatus = VaultStatus.locked) -> Vault:
        """
        Create a new vault with device_id as the primary identifier.

        Args:
            device_id: Unique identifier from the ESP32 device
            name: Human-readable vault name
            location: Physical location of the vault
            status: Initial vault status (defaults to locked)

        Returns:
            Created Vault instance

        Raises:
            ValueError: If device_id already exists or is invalid
        """
        # Validate device_id format and uniqueness
        if not device_id or not device_id.strip():
            raise ValueError("device_id cannot be empty")

        # Check if device_id already exists
        existing_vault = self.repo.get_by_id(device_id)
        if existing_vault:
            raise ValueError(f"Vault with device_id '{device_id}' already exists")

        return self.repo.create(
            device_id=device_id,
            name=name,
            location=location,
            status=status
        )

    # Fetch a vault by ID (serial number)
    def get_vault_by_id(self, vault_id: int) -> Vault | None:
        return self.repo.get_by_id(vault_id)

    # Fetch a vault by name
    def get_vault_by_name(self, name: str) -> Vault | None:
        return self.repo.get_by_name(name)

    # List all vaults
    def list_vaults(self) -> list[Vault]:
        return self.repo.get_all()

    # Delete a vault by ID (serial number)
    def delete_vault(self, vault_id: int) -> Vault | None:
        return self.repo.delete(vault_id)

    # Update a vault's status
    def update_vault_status(self, vault_id: int, status: VaultStatus) -> Vault | None:
        return self.repo.update(vault_id, status=status)

    # Optional: restore a soft-deleted vault
    def restore_vault(self, vault_id: int) -> Vault | None:
        return self.repo.restore(vault_id)

    # Hard delete a vault (permanent removal)
    def hard_delete_vault(self, vault_id: int) -> Vault | None:
        """
        Permanently delete a vault and all associated data.
        WARNING: This action cannot be undone!
        """
        return self.repo.hard_delete(vault_id)
