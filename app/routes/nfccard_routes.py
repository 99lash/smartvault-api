from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.services.NfcCardService import NfcCardService
from app.services.users.UserService import UserService
from app.models.User import User
from app.schemas.nfc_card import NfcCardCreate, NfcCardAssign, NfcCardRead, NfcCardWithUser
from app.schemas.Response import Response
from app.core.dependencies import get_current_admin, get_current_user
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.services.VaultAccessControlService import VaultAccessControlService
from app.models.VaultMembership import MembershipRole

router = APIRouter(
    prefix="/nfc-cards",
    tags=["NFC Cards"],
    redirect_slashes=False  
)


# -----------------------------
# Get all NFC cards with usernames
# -----------------------------
@router.get("/users", response_model=List[NfcCardWithUser])
def list_nfc_cards_with_users(db: Session = Depends(get_db), current_user = Depends(get_current_admin)):
    """
    Returns all NFC cards with their assigned usernames.
    - Admin access is required.
    """
    service = NfcCardService(db)
    cards_with_users = service.get_all_cards_with_users()
    return [NfcCardWithUser(nfc_card_id=card.id, nfc_card_uid=card.uid, nfc_card_name=card.name, vault_id=card.vault_id, user_id=card.user_id, username=username) for card, username in cards_with_users]

# -----------------------------
# Create a new NFC card
# -----------------------------
@router.post("/", response_model=Response[NfcCardRead], status_code=status.HTTP_201_CREATED)
def create_nfc_card(payload: NfcCardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Creates a new NFC card record with role-based access control.
    
    Role-based behavior:
    - MEMBER: Limited to 1 NFC card per vault, automatically assigned to themselves
    - ADMIN: Unlimited NFC cards, can assign to any vault member or leave unassigned
    - GUEST: Cannot create NFC cards (read-only access)
    
    Args:
        payload: NFC card creation data including uid, vault_id, name, and optional user_id
        current_user: Currently authenticated user
        db: Database session
    """
    # Initialize access control service
    access_control = VaultAccessControlService(db)
    
    # Check vault membership and get user role
    is_member, role = access_control.check_vault_access_and_role(current_user.id, payload.vault_id)
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this vault"
        )
    
    # Enforce role-based limits
    access_control.enforce_nfc_card_limit(current_user.id, payload.vault_id)
    
    # Determine user_id based on role
    if role == MembershipRole.member:
        # Members must have the card assigned to themselves
        user_id = current_user.id
    elif role == MembershipRole.admin:
        # Admins can choose to assign or leave unassigned
        user_id = payload.user_id
    else:
        # Guests cannot create cards (should be caught by enforce_nfc_card_limit)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot create NFC cards"
        )
    
    # Create the NFC card
    service = NfcCardService(db)
    nfc_card = service.create_card(
        uid=payload.uid,
        vault_id=payload.vault_id,
        name=payload.name,
        user_id=user_id
    )
    
    # Prepare response message based on role
    if role == MembershipRole.member:
        detail = "NFC Card successfully created and assigned to you"
    else:
        assignment_msg = f" and assigned to user {user_id}" if user_id else " (unassigned)"
        detail = f"NFC Card successfully created{assignment_msg}"
    
    return Response(success=True, data=nfc_card, detail=detail)

# -----------------------------
# Get all NFC cards
# -----------------------------
@router.get("/", response_model=List[NfcCardRead])
def list_nfc_cards(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all NFC cards.
    - Could later exclude soft-deleted records.
    """
    service = NfcCardService(db)
    return service.get_all_cards()

# -----------------------------
# Get NFC card by UID
# -----------------------------
@router.get("/uid/{uid}", response_model=NfcCardRead)
def get_card_by_uid(uid: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch a single NFC card by UID.
    - Raises 404 if not found.
    """
    service = NfcCardService(db)
    card = service.get_card_by_uid(uid)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    return card

# -----------------------------
# Get all cards assigned to a user
# -----------------------------
@router.get("/user/{user_id}", response_model=List[NfcCardRead])
def get_cards_by_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch user all NFC cards.
    - Raises 404 if user not found.  
    """
    user = UserService(db).get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    service = NfcCardService(db)
    return service.get_cards_by_user(user_id)

# -----------------------------
# Assign card to user
# -----------------------------
@router.patch("/{card_id}/assign", response_model=Response)
def assign_card_to_user(card_id: int, payload: NfcCardAssign, db: Session = Depends(get_db), current_user = Depends(get_current_admin)):
    """
    Assigns an existing NFC card to a user.
    - Updates the `user_id` field.
    - Raises 404 if NFC card or user not found.
    """
    userService = UserService(db)
    user = userService.get_user_by_id(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    nfcCardService = NfcCardService(db)
    card = nfcCardService.assign_card_to_user(card_id, payload.user_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    
    return Response(success=True, detail=f"NFC Card {card_id} assigned to user {payload.user_id}")

# -----------------------------
# Get all NFC cards for a specific vault with usernames
# -----------------------------
@router.get("/vault/{vault_id}", response_model=List[NfcCardWithUser])
def get_cards_by_vault(vault_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch all NFC cards for a specific vault with usernames.
    - User must be a member of the vault to view cards
    """
    # Check if user has access to the vault
    vault_service = VaultMembershipService(db)
    if not vault_service.is_user_member_of_vault(current_user.id, vault_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User does not have access to vault {vault_id}"
        )
    
    service = NfcCardService(db)
    cards_with_users = service.get_cards_by_vault_with_users(vault_id)
    
    # Use the NfcCardWithUser schema format (same as /users endpoint)
    return [
        NfcCardWithUser(
            nfc_card_id=card.id,
            nfc_card_uid=card.uid,
            nfc_card_name=card.name,
            vault_id=card.vault_id,
            user_id=card.user_id,
            username=username or "Unassigned"  # Provide default if username is None
        ) 
        for card, username in cards_with_users
    ]
# -----------------------------
# Hard delete a NFC card (permanent deletion)
# -----------------------------
@router.delete("/{card_id}/hard", response_model=Response)
def hard_delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Permanently deletes an NFC card by ID.
    - WARNING: This action cannot be undone!
    - Raises 404 if not found.
    - Requires vault admin access for the vault containing the NFC card.
    """
    print(f"🔍 Delete attempt by user: {current_user.id} ({current_user.username}), system role: {current_user.role}")
    
    # Get the NFC card to find its vault
    service = NfcCardService(db)
    nfc_card = service.get_card_by_id(card_id)
    if not nfc_card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    
    print(f"🔍 NFC card found: ID={nfc_card.id}, UID={nfc_card.uid}, Vault ID={nfc_card.vault_id}")
    
    # Check if user is admin of the vault containing this NFC card
    from app.services.vaults.VaultMembershipService import VaultMembershipService
    from app.models.VaultMembership import MembershipRole
    
    membership_service = VaultMembershipService(db)
    user_role_in_vault = membership_service.get_user_role_in_vault(current_user.id, nfc_card.vault_id)
    
    print(f"🔍 User role in vault {nfc_card.vault_id}: {user_role_in_vault}")
    
    if user_role_in_vault != MembershipRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Vault admin access required. User role in vault: {user_role_in_vault}"
        )
    
    # Proceed with deletion
    deleted = service.hard_delete_card(card_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    
    print(f"✅ NFC card {card_id} permanently deleted by user {current_user.id}")
    return Response(success=True, detail=f"NFC card {card_id} permanently deleted")

# -----------------------------
# Soft delete a NFC card
# -----------------------------
@router.delete("/{card_id}", response_model=Response)
def delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Deletes an NFC card by ID.
    - Soft deletes if the model has a deleted_at column.
    - Raises 404 if not found.
    - Requires vault admin access for the vault containing the NFC card.
    """
    print(f"🔍 Soft delete attempt by user: {current_user.id} ({current_user.username}), system role: {current_user.role}")
    
    # Get the NFC card to find its vault
    service = NfcCardService(db)
    nfc_card = service.get_card_by_id(card_id)
    if not nfc_card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    
    print(f"🔍 NFC card found: ID={nfc_card.id}, UID={nfc_card.uid}, Vault ID={nfc_card.vault_id}")
    
    # Check if user is admin of the vault containing this NFC card
    from app.services.vaults.VaultMembershipService import VaultMembershipService
    from app.models.VaultMembership import MembershipRole
    
    membership_service = VaultMembershipService(db)
    user_role_in_vault = membership_service.get_user_role_in_vault(current_user.id, nfc_card.vault_id)
    
    print(f"🔍 User role in vault {nfc_card.vault_id}: {user_role_in_vault}")
    
    if user_role_in_vault != MembershipRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=f"Vault admin access required. User role in vault: {user_role_in_vault}"
        )
    
    # Proceed with deletion
    card = service.delete_card(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    
    print(f"✅ NFC card {card_id} soft deleted by user {current_user.id}")
    return Response(success=True, detail=f"NFC card {card_id} deleted successfully")
