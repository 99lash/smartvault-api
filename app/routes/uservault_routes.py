from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.Response import Response
from app.schemas.user_vault import UserVaultCreate, UserVaultRead, UserVaultBulkCreate
from app.schemas.vault import VaultRead
from app.schemas.user import UserRead
from app.services.UserVaultService import UserVaultService

# -----------------------------
# FastAPI router for UserVault endpoints
# -----------------------------
# Handles all HTTP requests related to user-vault associations:
# - create association (add user to vault)
# - list associations
# - fetch by ID
# - delete association (remove user from vault)
# - get vaults for user
# - get users for vault
# - bulk add users to vault
# - check access
router = APIRouter(prefix="/user-vaults", tags=["user-vaults"])

# -----------------------------
# Create a user-vault association
# -----------------------------
@router.post("/", response_model=Response[UserVaultRead], status_code=status.HTTP_201_CREATED)
def create_association(payload: UserVaultCreate, db: Session = Depends(get_db)):
    """
    Creates a user-vault association (adds user to vault).
    - Validates no existing association.
    - Raises 400 if user already has access.
    """
    service = UserVaultService(db)
    try:
        association = service.add_user_to_vault(payload.user_id, payload.vault_id)
        return Response(success=True, data=association, detail='User added to vault successfully.')
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# -----------------------------
# Bulk create associations (add multiple users to vault)
# -----------------------------
@router.post("/bulk", response_model=Response[List[UserVaultRead]])
def bulk_create_associations(payload: UserVaultBulkCreate, db: Session = Depends(get_db)):
    """
    Adds multiple users to a vault.
    - Skips users who already have access.
    """
    service = UserVaultService(db)
    associations = service.add_users_to_vault(payload.user_ids, payload.vault_id)
    return Response(success=True, data=associations, detail=f'{len(associations)} users added to vault.')

# -----------------------------
# List all user-vault associations
# -----------------------------
@router.get("/", response_model=List[UserVaultRead])
def list_associations(db: Session = Depends(get_db)):
    """
    Returns all user-vault associations.
    """
    service = UserVaultService(db)
    return service.get_all_associations()

# -----------------------------
# Get association by ID
# -----------------------------
@router.get("/{association_id}", response_model=UserVaultRead)
def get_association(association_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single user-vault association by ID.
    - Raises 404 if not found.
    """
    service = UserVaultService(db)
    association = service.get_association_by_id(association_id)
    if not association:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Association not found")
    return association

# -----------------------------
# Delete association by user and vault IDs
# -----------------------------
@router.delete("/{user_id}/{vault_id}", response_model=Response)
def delete_association(user_id: int, vault_id: int, db: Session = Depends(get_db)):
    """
    Removes a user from a vault.
    - Raises 404 if association not found.
    """
    service = UserVaultService(db)
    if not service.remove_user_from_vault(user_id, vault_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Association not found")
    return Response(success=True, detail='User removed from vault successfully.')

# -----------------------------
# Get vaults for a user
# -----------------------------
@router.get("/users/{user_id}/vaults", response_model=List[VaultRead])
def get_vaults_for_user(user_id: int, db: Session = Depends(get_db)):
    """
    Returns all vaults accessible to a user.
    - Raises 404 if user not found (optional, implement if needed).
    """
    service = UserVaultService(db)
    return service.get_vaults_for_user(user_id)

# -----------------------------
# Get users for a vault
# -----------------------------
@router.get("/vaults/{vault_id}/users", response_model=List[UserRead])
def get_users_for_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Returns all users with access to a vault.
    - Raises 404 if vault not found (optional).
    """
    service = UserVaultService(db)
    return service.get_users_for_vault(vault_id)

# -----------------------------
# Check user access to vault
# -----------------------------
@router.get("/access/{user_id}/{vault_id}", response_model=Response[bool])
def check_access(user_id: int, vault_id: int, db: Session = Depends(get_db)):
    """
    Checks if a user has access to a vault.
    """
    service = UserVaultService(db)
    has_access = service.has_user_access_to_vault(user_id, vault_id)
    return Response(success=True, data=has_access, detail="Access check completed.")