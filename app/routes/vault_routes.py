from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.vault_service import VaultService
from app.models.Vault import VaultStatus

# -----------------------------
# FastAPI router for Vault endpoints
# -----------------------------
# Handles all HTTP requests related to vaults:
# - create
# - list
# - fetch by ID
# - soft delete
# - status updates
router = APIRouter(prefix="/vaults", tags=["vaults"])

# -----------------------------
# Create a new vault
# -----------------------------
@router.post("/")
def create_vault(name: str, location: str | None = None, db: Session = Depends(get_db)):
    """
    Creates a new vault.
    - Default status is 'locked'.
    """
    service = VaultService(db)
    return service.create_vault(name=name, location=location)

# -----------------------------
# List all vaults
# -----------------------------
@router.get("/")
def list_vaults(db: Session = Depends(get_db)):
    """
    Returns all vaults.
    """
    service = VaultService(db)
    return service.list_vaults()

# -----------------------------
# Get a vault by ID
# -----------------------------
@router.get("/{vault_id}")
def get_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single vault by ID.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    return vault

# -----------------------------
# Soft delete a vault
# -----------------------------
@router.delete("/{vault_id}")
def delete_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Soft deletes a vault by ID.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.delete_vault(vault_id)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    return {"message": f"Vault {vault_id} deleted successfully"}

# -----------------------------
# Update a vault's status
# -----------------------------
@router.patch("/{vault_id}/status")
def update_vault_status(vault_id: int, status: VaultStatus, db: Session = Depends(get_db)):
    """
    Update the status of a vault.
    - Example: locked, unlocked, tampered.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.update_vault_status(vault_id, status)
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    return {"message": f"Vault {vault_id} status updated to {status}"}
