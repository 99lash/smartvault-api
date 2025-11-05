from sqlalchemy.orm import Session
from app.repositories.VaultRepository import VaultRepository
from app.repositories.VaultInvitationRepository import VaultInvitationRepository
from app.repositories.VaultMembershipRepository import VaultMembershipRepository
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.services.logs.LogService import LogService
from app.models.Vault import Vault, VaultStatus
from app.models.VaultInvitation import InvitationRole, TransferType
from app.models.VaultMembership import MembershipRole
from app.models.Log import LogEventType
from fastapi import HTTPException, status

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
        self.vault_membership_service = VaultMembershipService(db)
        self.vault_invitation_repo = VaultInvitationRepository(db)
        self.vault_membership_repo = VaultMembershipRepository(db)
        self.log_service = LogService(db)

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

    def initiate_ownership_transfer(self, vault_id: int, current_owner_id: int, new_owner_user_id: int, transfer_type: TransferType):
        vault = self.repo.get_by_id(vault_id)
        if not vault:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

        # Ensure current_user is the actual owner (admin) of the vault
        if not self.vault_membership_service.is_user_admin_of_vault(current_owner_id, vault_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the vault owner can initiate ownership transfer.")

        # Ensure new_owner_user_id is a valid user and a member of the vault
        new_owner_membership = self.vault_membership_repo.get_membership_by_user_and_vault(new_owner_user_id, vault_id)
        if not new_owner_membership:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New owner must be an existing member of the vault.")

        # Prevent transferring to self
        if current_owner_id == new_owner_user_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer ownership to yourself.")

        # Check for existing pending transfer invitations for this vault
        existing_transfer_invitation = self.vault_invitation_repo.get_pending_ownership_transfer_invitation(vault_id)
        if existing_transfer_invitation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A pending ownership transfer already exists for this vault.")

        # Create a new VaultInvitation for ownership transfer
        self.vault_invitation_repo.create_ownership_transfer_invitation(
            vault_id=vault_id,
            invited_by=current_owner_id,
            new_owner_user_id=new_owner_user_id,
            transfer_type=transfer_type
        )

        self.log_service.create_log(
            device_id=vault.device_id,
            user_id=current_owner_id,
            event_type=LogEventType.ownership_transfer_initiated,
            details=f"Ownership transfer initiated by user {current_owner_id} to user {new_owner_user_id} with type {transfer_type.value}."
        )

    def accept_ownership_transfer(self, vault_id: int, new_owner_user_id: int, invite_code: str):
        vault = self.repo.get_by_id(vault_id)
        if not vault:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")

        # Retrieve and validate the ownership transfer invitation
        invitation = self.vault_invitation_repo.get_ownership_transfer_invitation_by_code(invite_code)

        if not invitation or not invitation.is_valid() or invitation.vault_id != vault_id or invitation.role != InvitationRole.admin:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired ownership transfer invitation.")

        if invitation.new_owner_user_id != new_owner_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not the designated recipient for this ownership transfer.")

        # Perform the ownership transfer atomically
        current_owner_membership = self.vault_membership_repo.get_membership_by_user_and_vault(invitation.invited_by, vault_id)
        new_owner_membership = self.vault_membership_repo.get_membership_by_user_and_vault(new_owner_user_id, vault_id)

        if not current_owner_membership or not new_owner_membership:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Vault memberships not found for transfer participants.")

        # 1. Promote new owner to admin
        self.vault_membership_repo.update_membership_role(new_owner_membership.id, MembershipRole.admin)

        # 2. Handle old owner's membership based on transfer_type
        if invitation.transfer_type == TransferType.full_transfer:
            self.vault_membership_repo.delete_membership(current_owner_membership.id)
            detail_message = f"Full ownership of vault {vault_id} transferred from user {invitation.invited_by} to user {new_owner_user_id}. Old owner removed."
        elif invitation.transfer_type == TransferType.shared_access:
            self.vault_membership_repo.update_membership_role(current_owner_membership.id, MembershipRole.member)
            detail_message = f"Shared ownership of vault {vault_id} transferred from user {invitation.invited_by} to user {new_owner_user_id}. Old owner demoted to member."
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid transfer type specified in invitation.")

        # 3. Mark invitation as accepted
        self.vault_invitation_repo.mark_invitation_as_accepted(invitation.id)

        self.log_service.create_log(
            device_id=vault.device_id,
            user_id=new_owner_user_id,
            event_type=LogEventType.ownership_transfer_accepted,
            details=detail_message
        )

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
