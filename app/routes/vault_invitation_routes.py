from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, validator

from app.core.database import get_db
from app.services.VaultInvitationService import VaultInvitationService
from app.services.VaultMembershipService import VaultMembershipService
from app.services.UserService import UserService
from app.models.User import User
from app.models.VaultInvitation import InvitationRole
from app.schemas.Response import Response

# -----------------------------
# Request/Response Schemas for Vault Invitations
# -----------------------------

class VaultInvitationCreate(BaseModel):
    """Request schema for creating vault invitations"""
    vault_id: int
    role: str = "member"  # Accept string values and convert to enum
    expires_in_hours: int = 24

    @validator('role')
    def validate_role(cls, v):
        valid_roles = ["admin", "member", "guest"]
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v

    @validator('expires_in_hours')
    def validate_expiry(cls, v):
        if v < 1 or v > 168:  # Max 1 week
            raise ValueError('Expiration must be between 1 and 168 hours')
        return v

class VaultInvitationResponse(BaseModel):
    """Response schema for vault invitation details"""
    id: int
    vault_id: int
    invited_by: int
    invite_code: str
    role: str
    expires_at: datetime
    accepted: bool
    created_at: datetime
    is_expired: bool
    is_valid: bool

class VaultInvitationAccept(BaseModel):
    """Request schema for accepting invitations"""
    invite_code: str

class VaultInvitationList(BaseModel):
    """Response schema for listing invitations"""
    invitations: List[VaultInvitationResponse]
    total: int

# -----------------------------
# FastAPI Router for Vault Invitation Endpoints
# -----------------------------
router = APIRouter(prefix="/vault-invitations", tags=["vault_invitations"])

# -----------------------------
# Create a new vault invitation
# -----------------------------
@router.post("/", response_model=Response[VaultInvitationResponse], status_code=status.HTTP_201_CREATED)
def create_vault_invitation(
    invitation_data: VaultInvitationCreate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Create a new vault invitation.

    **Requirements:**
    - User must be authenticated
    - User must have admin access to the vault
    - Invitation expires after specified hours
    - Generates unique UUID invitation code

    **Returns:** Invitation details with shareable code
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

        # Check if user has admin access to the vault
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, invitation_data.vault_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to create invitations"
            )

        # Convert string role to enum
        role_enum = InvitationRole(invitation_data.role)

        # Create the invitation
        invitation_service = VaultInvitationService(db)
        invitation = invitation_service.create_invitation(
            vault_id=invitation_data.vault_id,
            invited_by=current_user.id,
            role=role_enum,
            expires_in_hours=invitation_data.expires_in_hours
        )

        # Format response
        response_data = VaultInvitationResponse(
            id=invitation.id,
            vault_id=invitation.vault_id,
            invited_by=invitation.invited_by,
            invite_code=invitation.invite_code,
            role=invitation.role.value,
            expires_at=invitation.expires_at,
            accepted=invitation.accepted,
            created_at=invitation.created_at,
            is_expired=invitation.is_expired(),
            is_valid=invitation.is_valid()
        )

        return Response(
            success=True,
            data=response_data,
            detail=f"Invitation created successfully. Code: {invitation.invite_code}"
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Get invitation details by code
# -----------------------------
@router.get("/{invite_code}", response_model=Response[VaultInvitationResponse])
def get_invitation_details(
    invite_code: str,
    db: Session = Depends(get_db)
):
    """
    Get invitation details by invitation code.

    **Public endpoint** - Anyone with the code can check if it's valid
    (but only the intended recipient should accept it)
    """
    try:
        invitation_service = VaultInvitationService(db)
        invitation = invitation_service.get_invitation_by_code(invite_code)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found"
            )

        # Format response
        response_data = VaultInvitationResponse(
            id=invitation.id,
            vault_id=invitation.vault_id,
            invited_by=invitation.invited_by,
            invite_code=invitation.invite_code,
            role=invitation.role.value,
            expires_at=invitation.expires_at,
            accepted=invitation.accepted,
            created_at=invitation.created_at,
            is_expired=invitation.is_expired(),
            is_valid=invitation.is_valid()
        )

        return Response(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Accept a vault invitation
# -----------------------------
@router.post("/{invite_code}/accept", response_model=Response[dict])
def accept_vault_invitation(
    invite_code: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Accept a vault invitation and join the vault.

    **Requirements:**
    - User must be authenticated
    - Invitation must exist and be valid
    - Invitation must not be expired
    - Invitation must not be already accepted
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

        invitation_service = VaultInvitationService(db)

        # Validate invitation first
        validation = invitation_service.validate_invitation_for_acceptance(invite_code)
        if not validation["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation["reason"]
            )

        # Accept the invitation (creates membership automatically)
        accepted_invitation = invitation_service.accept_invitation(invite_code)

        return Response(
            success=True,
            data={
                "message": "Successfully joined vault",
                "vault_id": accepted_invitation.vault_id,
                "role": accepted_invitation.role.value,
                "invitation_id": accepted_invitation.id
            },
            detail=f"Welcome to the vault! You now have {accepted_invitation.role.value} access."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Delete a vault invitation
# -----------------------------
@router.delete("/{invite_code}", response_model=Response)
def delete_vault_invitation(
    invite_code: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Delete a vault invitation.

    **Requirements:**
    - User must be authenticated
    - User must be the admin who created the invitation, OR
    - User must have admin access to the vault
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

        invitation_service = VaultInvitationService(db)
        invitation = invitation_service.get_invitation_by_code(invite_code)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invitation not found"
            )

        # Check permissions: either the inviter or a vault admin can delete
        membership_service = VaultMembershipService(db)
        is_inviter = invitation.invited_by == current_user.id
        is_vault_admin = membership_service.is_user_admin_of_vault(current_user.id, invitation.vault_id)

        if not (is_inviter or is_vault_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the inviter or vault admin can delete invitations"
            )

        # Delete the invitation
        deleted = invitation_service.delete_invitation(invite_code)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete invitation"
            )

        return Response(
            success=True,
            detail=f"Invitation {invite_code} deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# List invitations for a vault
# -----------------------------
@router.get("/vault/{vault_id}", response_model=Response[VaultInvitationList])
def list_vault_invitations(
    vault_id: str,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    List all invitations for a specific vault.

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

        # Check if user has access to the vault
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, vault_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required to view invitations"
            )

        invitation_service = VaultInvitationService(db)
        invitations = invitation_service.get_vault_invitations(vault_id)

        # Format response
        formatted_invitations = []
        for invitation in invitations:
            formatted_invitations.append(VaultInvitationResponse(
                id=invitation.id,
                vault_id=invitation.vault_id,
                invited_by=invitation.invited_by,
                invite_code=invitation.invite_code,
                role=invitation.role.value,
                expires_at=invitation.expires_at,
                accepted=invitation.accepted,
                created_at=invitation.created_at,
                is_expired=invitation.is_expired(),
                is_valid=invitation.is_valid()
            ))

        response_data = VaultInvitationList(
            invitations=formatted_invitations,
            total=len(formatted_invitations)
        )

        return Response(success=True, data=response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# -----------------------------
# Clean up expired invitations (admin only)
# -----------------------------
@router.delete("/cleanup/expired", response_model=Response)
def cleanup_expired_invitations(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Clean up all expired invitations across all vaults.

    **Requirements:**
    - User must be authenticated
    - User must have admin role (system-wide admin)
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

        # Check if user is system admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System admin role required for cleanup operations"
            )

        invitation_service = VaultInvitationService(db)
        deleted_count = invitation_service.cleanup_expired_invitations()

        return Response(
            success=True,
            detail=f"Cleaned up {deleted_count} expired invitations"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))