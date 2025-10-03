from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.services.VaultService import VaultService
from app.services.VaultMembershipService import VaultMembershipService
from app.services.UserService import UserService
from app.models.VaultMembership import MembershipRole
from app.schemas.vault import VaultCreate, UpdateVaultStatus, VaultRead
from app.schemas.Response import Response
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
def create_vault(
    payload: VaultCreate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Create a new vault with device_id as the primary identifier.

    The vault ID will be the same as the device_id, ensuring direct mapping
    between the physical ESP32 device and the vault record.

    Args:
        payload: VaultCreate schema containing device_id, name, location, status
        authorization: Bearer token for authentication
        db: Database session

    Returns:
        Response with created vault data and success message

    Raises:
        HTTPException: If authentication fails or vault creation fails
    """
    # Validate authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to create vault"
        )

    token = authorization.split(" ")[1]
    user_service = UserService(db)
    current_user = user_service.validate_token(token)

    try:
        # Create the vault with device_id as primary identifier
        service = VaultService(db)
        vault = service.create_vault(
            device_id=payload.device_id,
            name=payload.name,
            location=payload.location,
            status=payload.status
        )

        # Automatically create admin membership for the creator
        membership_service = VaultMembershipService(db)
        membership = membership_service.add_user_to_vault(
            user_id=current_user.id,
            vault_id=vault.id,  # This will be the device_id
            role=MembershipRole.admin
        )

        return Response(
            success=True,
            data=vault,
            detail=f"Vault '{vault.name}' created successfully with device ID '{vault.id}'. You have admin access to this vault."
        )

    except ValueError as e:
        # Handle validation errors (e.g., duplicate device_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create vault: {str(e)}"
        )

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
def get_vault(vault_id: str, db: Session = Depends(get_db)):
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
def delete_vault(vault_id: str, db: Session = Depends(get_db)):
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
# Hard delete a vault (permanent deletion)
# -----------------------------
@router.delete("/{vault_id}/hard", response_model=Response)
def hard_delete_vault(
    vault_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Permanently deletes a vault and all associated data.
    - WARNING: This action cannot be undone!
    - Requires authentication and admin access to the vault.
    - Raises 404 if vault not found.
    """
    # Manual token validation
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    token = authorization.split(" ")[1]
    user_service = UserService(db)
    current_user = user_service.validate_token(token)

    # Check if user has admin access to the vault
    membership_service = VaultMembershipService(db)
    if not membership_service.is_user_admin_of_vault(current_user.id, vault_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to hard delete vault"
        )

    # Hard delete the vault (removes from database completely)
    service = VaultService(db)
    vault = service.hard_delete_vault(vault_id)
    if not vault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

    return Response(
        success=True,
        detail=f"Vault {vault_id} permanently deleted (this action cannot be undone)"
    )

# -----------------------------
# Update a vault's status
# -----------------------------
@router.patch("/{vault_id}/status", response_model=Response)
def update_vault_status(vault_id: str, payload: UpdateVaultStatus, db: Session = Depends(get_db)):
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