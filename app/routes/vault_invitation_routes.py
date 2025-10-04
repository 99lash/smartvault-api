from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from pydantic import BaseModel, validator

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_admin
from app.services.vaults.VaultInvitationService import VaultInvitationService
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.models.User import User
from app.models.VaultInvitation import InvitationRole
from app.schemas.Response import Response

# -----------------------------
# Request/Response Schemas for Vault Invitations
# -----------------------------

class VaultInvitationCreate(BaseModel):
    vault_id: int
    role: str = "member"
    expires_in_hours: int = 24

    @validator("role")
    def validate_role(cls, v):
        valid_roles = ["admin", "member", "guest"]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v

    @validator("expires_in_hours")
    def validate_expiry(cls, v):
        if v < 1 or v > 168:
            raise ValueError("Expiration must be between 1 and 168 hours")
        return v


class VaultInvitationResponse(BaseModel):
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
    invite_code: str


class VaultInvitationList(BaseModel):
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, invitation_data.vault_id):
            raise HTTPException(status_code=403, detail="Admin access required to create invitations")

        role_enum = InvitationRole(invitation_data.role)
        invitation_service = VaultInvitationService(db)

        invitation = invitation_service.create_invitation(
            vault_id=invitation_data.vault_id,
            invited_by=current_user.id,
            role=role_enum,
            expires_in_hours=invitation_data.expires_in_hours,
        )

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
            is_valid=invitation.is_valid(),
        )

        return Response(success=True, data=response_data, detail=f"Invitation created successfully. Code: {invitation.invite_code}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------
# Get invitation details by code
# -----------------------------
@router.get("/{invite_code}", response_model=Response[VaultInvitationResponse])
def get_invitation_details(invite_code: str, db: Session = Depends(get_db)):
    try:
        invitation_service = VaultInvitationService(db)
        invitation = invitation_service.get_invitation_by_code(invite_code)

        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

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
            is_valid=invitation.is_valid(),
        )

        return Response(success=True, data=response_data)

    except HTTPException:
        raise


# -----------------------------
# Accept a vault invitation
# -----------------------------
@router.post("/{invite_code}/accept", response_model=Response[dict])
def accept_vault_invitation(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation_service = VaultInvitationService(db)

    validation = invitation_service.validate_invitation_for_acceptance(invite_code)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["reason"])

    accepted_invitation = invitation_service.accept_invitation(invite_code, current_user.id)

    return Response(
        success=True,
        data={
            "message": "Successfully joined vault",
            "vault_id": accepted_invitation.vault_id,
            "role": accepted_invitation.role.value,
            "invitation_id": accepted_invitation.id,
        },
        detail=f"Welcome to the vault! You now have {accepted_invitation.role.value} access.",
    )


# -----------------------------
# Delete a vault invitation
# -----------------------------
@router.delete("/{invite_code}", response_model=Response)
def delete_vault_invitation(
    invite_code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    invitation_service = VaultInvitationService(db)
    invitation = invitation_service.get_invitation_by_code(invite_code)

    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    membership_service = VaultMembershipService(db)
    is_inviter = invitation.invited_by == current_user.id
    is_vault_admin = membership_service.is_user_admin_of_vault(current_user.id, invitation.vault_id)

    if not (is_inviter or is_vault_admin):
        raise HTTPException(status_code=403, detail="Only the inviter or vault admin can delete invitations")

    deleted = invitation_service.delete_invitation(invite_code)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete invitation")

    return Response(success=True, detail=f"Invitation {invite_code} deleted successfully")


# -----------------------------
# List invitations for a vault
# -----------------------------
@router.get("/vault/{vault_id}", response_model=Response[VaultInvitationList])
def list_vault_invitations(
    vault_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership_service = VaultMembershipService(db)
    if not membership_service.is_user_admin_of_vault(current_user.id, vault_id):
        raise HTTPException(status_code=403, detail="Admin access required to view invitations")

    invitation_service = VaultInvitationService(db)
    invitations = invitation_service.get_vault_invitations(vault_id)

    formatted_invitations = [
        VaultInvitationResponse(
            id=i.id,
            vault_id=i.vault_id,
            invited_by=i.invited_by,
            invite_code=i.invite_code,
            role=i.role.value,
            expires_at=i.expires_at,
            accepted=i.accepted,
            created_at=i.created_at,
            is_expired=i.is_expired(),
            is_valid=i.is_valid(),
        )
        for i in invitations
    ]

    return Response(success=True, data=VaultInvitationList(invitations=formatted_invitations, total=len(formatted_invitations)))


# -----------------------------
# Clean up expired invitations (admin only)
# -----------------------------
@router.delete("/cleanup/expired", response_model=Response)
def cleanup_expired_invitations(
    current_user: User = Depends(get_current_admin),  # 👈 auto-enforces system admin
    db: Session = Depends(get_db),
):
    invitation_service = VaultInvitationService(db)
    deleted_count = invitation_service.cleanup_expired_invitations()
    return Response(success=True, detail=f"Cleaned up {deleted_count} expired invitations")
