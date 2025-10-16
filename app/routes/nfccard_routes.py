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
    return [NfcCardWithUser(nfc_card_id=card.id, nfc_card_uid=card.uid, nfc_card_name=card.name, username=username) for card, username in cards_with_users]

# -----------------------------
# Create a new NFC card
# -----------------------------
@router.post("/", response_model=Response[NfcCardRead], status_code=status.HTTP_201_CREATED)
def create_nfc_card(payload: NfcCardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Creates a new nfc card record.
    - Requires a NFC card uid and vault_id
    - user_id is optional (can be None if unassigned)
    - User must be an admin of the specified vault
    """
    # Check if user is an admin of the specified vault
    vault_service = VaultMembershipService(db)
    if not vault_service.is_user_admin_of_vault(current_user.id, payload.vault_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User must be an admin of vault {payload.vault_id} to register NFC cards"
        )

    service = NfcCardService(db)
    nfcCard = service.create_card(uid=payload.uid, name=payload.name, user_id=payload.user_id)
    return Response(success=True, data=nfcCard, detail="NFC Card successfully created")

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
            username=username or "Unassigned"  # Provide default if username is None
        ) 
        for card, username in cards_with_users
    ]
# -----------------------------
# Hard delete a NFC card (permanent deletion)
# -----------------------------
@router.delete("/{card_id}/hard", response_model=Response)
def hard_delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_admin)):
    """
    Permanently deletes an NFC card by ID.
    - WARNING: This action cannot be undone!
    - Raises 404 if not found.
    """
    service = NfcCardService(db)
    deleted = service.hard_delete_card(card_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    return Response(success=True, detail=f"NFC card {card_id} permanently deleted")

# -----------------------------
# Soft delete a NFC card
# -----------------------------
@router.delete("/{card_id}", response_model=Response)
def delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_admin)):
    """
    Deletes an NFC card by ID.
    - Soft deletes if the model has a deleted_at column.
    - Raises 404 if not found.
    """
    service = NfcCardService(db)
    card = service.delete_card(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")
    return Response(success=True, detail=f"NFC card {card_id} deleted successfully")
