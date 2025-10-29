from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.services.VaultAccessControlService import VaultAccessControlService
from app.models.User import User
from app.models.Vault import Vault
from app.models.VaultMembership import MembershipRole
from app.schemas.Response import Response

# -----------------------------
# Schemas
# -----------------------------
class VaultMembershipCreate(BaseModel):
    user_id: int
    vault_id: int
    role: str = "member"

class VaultMembershipUpdate(BaseModel):
    role: str

class VaultMembershipResponse(BaseModel):
    id: int
    user_id: int
    vault_id: int
    vault_name: str | None
    vault_device_id: str | None
    vault_location: str | None
    role: str
    created_at: str
    updated_at: str | None
    username: str | None
    first_name: str | None
    last_name: str | None
    last_access: str | None = None  # Timestamp of user's last successful access to this vault

# -----------------------------
# Router
# -----------------------------
router = APIRouter(prefix="/vault-memberships", tags=["vault_memberships"])


# -----------------------------
# Add a user to a vault
# -----------------------------
@router.post("/", response_model=Response[VaultMembershipResponse], status_code=status.HTTP_201_CREATED)
def add_user_to_vault(
    membership_data: VaultMembershipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)

    if not membership_service.is_user_admin_of_vault(current_user.id, membership_data.vault_id):
        raise HTTPException(status_code=403, detail="Admin access required to add users to vault")

    try:
        role_enum = MembershipRole(membership_data.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {[r.value for r in MembershipRole]}"
        )

    membership = membership_service.add_user_to_vault(
        user_id=membership_data.user_id,
        vault_id=membership_data.vault_id,
        role=role_enum
    )

    # Fetch vault details for consistent response
    vault = db.query(Vault).filter(Vault.id == membership.vault_id).first()

    response_data = VaultMembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        vault_id=membership.vault_id,
        vault_name=vault.name if vault else None,
        vault_device_id=vault.device_id if vault else None,
        vault_location=vault.location if vault else None,
        role=membership.role.value,
        created_at=membership.created_at.isoformat(),
        updated_at=membership.updated_at.isoformat() if membership.updated_at else None,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name
    )

    return Response(success=True, data=response_data,
        detail=f"User {membership_data.user_id} added to vault {membership_data.vault_id} with {membership_data.role} role")


# -----------------------------
# Update user role
# -----------------------------
@router.put("/{user_id}/vault/{vault_id}", response_model=Response[VaultMembershipResponse])
def update_user_role_in_vault(
    user_id: int,
    vault_id: int,
    role_data: VaultMembershipUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)

    if not membership_service.is_user_admin_of_vault(current_user.id, vault_id):
        raise HTTPException(status_code=403, detail="Admin access required to update user roles")

    try:
        role_enum = MembershipRole(role_data.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {[r.value for r in MembershipRole]}"
        )

    membership = membership_service.change_user_role(user_id, vault_id, role_enum)
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member of this vault")

    # Fetch vault details for consistent response
    vault = db.query(Vault).filter(Vault.id == membership.vault_id).first()

    response_data = VaultMembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        vault_id=membership.vault_id,
        vault_name=vault.name if vault else None,
        vault_device_id=vault.device_id if vault else None,
        vault_location=vault.location if vault else None,
        role=membership.role.value,
        created_at=membership.created_at.isoformat(),
        updated_at=membership.updated_at.isoformat() if membership.updated_at else None,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name
    )

    return Response(success=True, data=response_data,
        detail=f"User {user_id} role updated to {role_data.role} in vault {vault_id}")


# -----------------------------
# Check if current user is admin of vault
# -----------------------------
@router.get("/vaults/{vault_id}/admin-check", response_model=Response)
def check_vault_admin(
    vault_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)
    is_admin = membership_service.is_user_admin_of_vault(current_user.id, vault_id)
    return Response(success=True, data={"is_admin": is_admin}, detail=f"Admin check completed for vault {vault_id}")


# -----------------------------
# Get all members of a vault
# -----------------------------
@router.get("/vault/{vault_id}", response_model=Response[List[VaultMembershipResponse]])
def get_vault_members(
    vault_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)
    user_role = membership_service.get_user_role_in_vault(current_user.id, vault_id)
    if not user_role:
        raise HTTPException(status_code=403, detail="Access denied to this vault")

    members = membership_service.get_vault_members(vault_id)
    # Fetch vault details once for response enrichment
    vault = db.query(Vault).filter(Vault.id == vault_id).first()

    response_data = []
    for member in members:
        user = db.query(User).filter(User.id == member.user_id).first()
        response_data.append(VaultMembershipResponse(
            id=member.id,
            user_id=member.user_id,
            vault_id=member.vault_id,
            vault_name=vault.name if vault else None,
            vault_device_id=vault.device_id if vault else None,
            vault_location=vault.location if vault else None,
            role=member.role.value,
            created_at=member.created_at.isoformat(),
            updated_at=member.updated_at.isoformat() if member.updated_at else None,
            username=user.username if user else None,
            first_name=user.first_name if user else None,
            last_name=user.last_name if user else None
        ))

    return Response(success=True, data=response_data)


# -----------------------------
# Remove a user from a vault
# -----------------------------
@router.delete("/{user_id}/vault/{vault_id}", response_model=Response)
def remove_user_from_vault(
    user_id: int,
    vault_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)

    is_admin = membership_service.is_user_admin_of_vault(current_user.id, vault_id)
    is_self = current_user.id == user_id

    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="Admin access required to remove other users")

    removed = membership_service.remove_user_from_vault(user_id, vault_id)
    if not removed:
        raise HTTPException(status_code=404, detail="User is not a member of this vault")

    return Response(success=True, detail=f"User {user_id} removed from vault {vault_id}")

# -----------------------------
# Get current user's vaults
# -----------------------------
@router.get("/user/vaults", response_model=Response[List[VaultMembershipResponse]])
def get_current_user_vaults(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.Vault import Vault

    membership_service = VaultMembershipService(db)
    user_memberships = membership_service.get_user_vaults(current_user.id)

    response_data = []
    for membership in user_memberships:
        # Fetch vault details
        vault = db.query(Vault).filter(Vault.id == membership['vault_id']).first()

        response_data.append(VaultMembershipResponse(
            id=membership['id'],
            user_id=membership['user_id'],
            vault_id=membership['vault_id'],
            vault_name=vault.name if vault else None,
            vault_device_id=vault.device_id if vault else None,
            vault_location=vault.location if vault else None,
            role=membership['role'].value,
            created_at=membership['created_at'].isoformat(),
            updated_at=membership['updated_at'].isoformat() if membership['updated_at'] else None,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            last_access=membership['last_access'].isoformat() + 'Z' if membership['last_access'] else None
        ))

    return Response(success=True, data=response_data)


# -----------------------------
# Get access limits for current user in a vault
# -----------------------------
@router.get("/vaults/{vault_id}/access-limits", response_model=Response)
def get_access_limits(
    vault_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get current access limits and counts for the user in this vault.
    
    This endpoint provides comprehensive information about:
    - User's role in the vault
    - Current counts of NFC cards and keypad pins
    - Limits based on role (None for unlimited, number for limited)
    - Boolean flags indicating if user can create resources
    
    This information is designed for frontend consumption to:
    - Display appropriate UI controls
    - Show/hide create buttons
    - Display current usage vs limits
    - Provide user feedback about their permissions
    
    Args:
        vault_id: ID of the vault to check limits for
        current_user: Currently authenticated user
        db: Database session
        
    Returns:
        Response with access limits information including:
        - is_member: Whether user is a member of the vault
        - role: User's role in the vault (admin/member/guest)
        - nfc_cards: Current count, limit, and can_create flag
        - keypad_pins: Current count, limit, and can_create flag
    """
    access_control = VaultAccessControlService(db)
    
    # Get comprehensive limits information
    limits_info = access_control.get_user_limits_info(current_user.id, vault_id)
    
    if not limits_info["is_member"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this vault"
        )
    
    return Response(
        success=True,
        data=limits_info,
        detail=f"Access limits retrieved for vault {vault_id}"
    )
