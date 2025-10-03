from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.services.VaultMembershipService import VaultMembershipService
from app.services.UserService import UserService
from app.models.User import User
from app.models.VaultMembership import VaultMembership, MembershipRole
from app.schemas.Response import Response

# -----------------------------
# Request/Response Schemas for Vault Memberships
# -----------------------------

class VaultMembershipCreate(BaseModel):
    """Request schema for adding a user to a vault"""
    user_id: int
    vault_id: int
    role: str = "member"  # "admin", "member", or "guest"

class VaultMembershipUpdate(BaseModel):
    """Request schema for updating a user's role in a vault"""
    role: str  # "admin", "member", or "guest"

class VaultMembershipResponse(BaseModel):
    """Response schema for vault membership details"""
    id: int
    user_id: int
    vault_id: int
    role: str
    created_at: str
    updated_at: str | None

# -----------------------------
# FastAPI Router for Vault Membership Endpoints
# -----------------------------
router = APIRouter(prefix="/vault-memberships", tags=["vault_memberships"])

# -----------------------------
# Add a user to a vault
# -----------------------------
@router.post("/", response_model=Response[VaultMembershipResponse], status_code=status.HTTP_201_CREATED)
def add_user_to_vault(
    membership_data: VaultMembershipCreate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Add a user to a vault with specified role.

    **Requirements:**
    - User must be authenticated
    - User must be an admin of the vault
    """
    try:
        # Manual token validation
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        token = authorization.split(" ")[1]
        user_service = UserService(db)
        current_user = user_service.validate_token(token)

        # Check if current user is admin of the vault
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, membership_data.vault_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to add users to vault"
            )

        # Validate role
        try:
            role_enum = MembershipRole(membership_data.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {[r.value for r in MembershipRole]}"
            )

        # Add user to vault
        membership = membership_service.add_user_to_vault(
            user_id=membership_data.user_id,
            vault_id=membership_data.vault_id,
            role=role_enum
        )

        # Format response
        response_data = VaultMembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            vault_id=membership.vault_id,
            role=membership.role.value,
            created_at=membership.created_at.isoformat(),
            updated_at=membership.updated_at.isoformat() if membership.updated_at else None
        )

        return Response(
            success=True,
            data=response_data,
            detail=f"User {membership_data.user_id} added to vault {membership_data.vault_id} with {membership_data.role} role"
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Update a user's role in a vault
# -----------------------------
@router.put("/{user_id}/vault/{vault_id}", response_model=Response[VaultMembershipResponse])
def update_user_role_in_vault(
    user_id: int,
    vault_id: str,
    role_data: VaultMembershipUpdate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Update a user's role in a vault.

    **Requirements:**
    - User must be authenticated
    - User must be an admin of the vault
    """
    try:
        # Manual token validation
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        token = authorization.split(" ")[1]
        user_service = UserService(db)
        current_user = user_service.validate_token(token)

        # Check if current user is admin of the vault
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, vault_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to update user roles"
            )

        # Validate role
        try:
            role_enum = MembershipRole(role_data.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {[r.value for r in MembershipRole]}"
            )

        # Update user role
        membership = membership_service.change_user_role(user_id, vault_id, role_enum)

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this vault"
            )

        # Format response
        response_data = VaultMembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            vault_id=membership.vault_id,
            role=membership.role.value,
            created_at=membership.created_at.isoformat(),
            updated_at=membership.updated_at.isoformat() if membership.updated_at else None
        )

        return Response(
            success=True,
            data=response_data,
            detail=f"User {user_id} role updated to {role_data.role} in vault {vault_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Get all members of a vault
# -----------------------------
@router.get("/vault/{vault_id}", response_model=Response[List[VaultMembershipResponse]])
def get_vault_members(
    vault_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get all members of a vault.

    **Requirements:**
    - User must be authenticated
    - User must have access to the vault
    """
    try:
        # Manual token validation
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        token = authorization.split(" ")[1]
        user_service = UserService(db)
        current_user = user_service.validate_token(token)

        # Check if current user has access to the vault
        membership_service = VaultMembershipService(db)
        user_role = membership_service.get_user_role_in_vault(current_user.id, vault_id)
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this vault"
            )

        # Get vault members
        members = membership_service.get_vault_members(vault_id)

        # Format response
        response_data = []
        for member in members:
            response_data.append(VaultMembershipResponse(
                id=member.id,
                user_id=member.user_id,
                vault_id=member.vault_id,
                role=member.role.value,
                created_at=member.created_at.isoformat(),
                updated_at=member.updated_at.isoformat() if member.updated_at else None
            ))

        return Response(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Remove a user from a vault
# -----------------------------
@router.delete("/{user_id}/vault/{vault_id}", response_model=Response)
def remove_user_from_vault(
    user_id: int,
    vault_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Remove a user from a vault.

    **Requirements:**
    - User must be authenticated
    - User must be an admin of the vault (or removing themselves)
    """
    try:
        # Manual token validation
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )

        token = authorization.split(" ")[1]
        user_service = UserService(db)
        current_user = user_service.validate_token(token)

        # Check permissions
        membership_service = VaultMembershipService(db)
        is_admin = membership_service.is_user_admin_of_vault(current_user.id, vault_id)
        is_self = current_user.id == user_id

        if not (is_admin or is_self):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to remove other users from vault"
            )

        # Remove user from vault
        removed = membership_service.remove_user_from_vault(user_id, vault_id)

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not a member of this vault"
            )

        return Response(
            success=True,
            detail=f"User {user_id} removed from vault {vault_id}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))