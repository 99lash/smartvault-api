from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.VaultService import VaultService
from app.schemas.Vault import VaultCreate, UpdateVaultStatus, VaultRead
from app.models.Vault import VaultStatus
from app.schemas.Common import Response
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
@router.post("/", response_model=Response[VaultRead], status_code=status.HTTP_201_CREATED)
def create_vault(payload: VaultCreate, db: Session = Depends(get_db)):
    """
    Creates a new vault.
    - Default status is 'locked'.
    """
    service = VaultService(db)
    vault = service.create_vault(payload.name, payload.location)
    return Response(success=True, data=vault, detail="Vault created successfully")

# -----------------------------
# List all vaults
# -----------------------------
@router.get("/", response_model=list[VaultRead])
def list_vaults(db: Session = Depends(get_db)):
    """
    Returns all vaults.
    """
    service = VaultService(db)
    return service.list_vaults()

# -----------------------------
# Get a vault by ID
# -----------------------------
@router.get("/{vault_id}", response_model=VaultRead)
def get_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single vault by ID.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.get_vault_by_id(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    return vault

# -----------------------------
# Soft delete a vault
# -----------------------------
@router.delete("/{vault_id}", response_model=Response)
def delete_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Soft deletes a vault by ID.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.delete_vault(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    return Response(success=True, detail=f"Vault {vault_id} deleted successfully")

# -----------------------------
# Update a vault's status
# -----------------------------
@router.patch("/{vault_id}/status", response_model=Response)
def update_vault_status(vault_id: int, payload: UpdateVaultStatus, db: Session = Depends(get_db)):
    """
    Update the status of a vault.
    - Example: locked, unlocked, tampered.
    - Raises 404 if vault not found.
    """
    service = VaultService(db)
    vault = service.update_vault_status(vault_id, payload.status)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
    return Response(success=True, detail=f"Vault {vault_id} status updated to {payload.status}")