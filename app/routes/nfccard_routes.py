from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.services.NfcCardService import NfcCardService
from app.services.users.UserService import UserService
from app.schemas.nfc_card import NfcCardCreate, NfcCardAssign, NfcCardRead, NfcCardWithUser
from app.schemas.Response import Response
from app.core.dependencies import get_current_admin, get_current_user

router = APIRouter(prefix="/nfc-cards", tags=["NFC Cards"])

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
def create_nfc_card(payload: NfcCardCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Creates a new nfc card record.
    - Requires a NFC card uid 
    - user_id is optional (can be None if unassigned) 
    """
    service = NfcCardService(db)
    nfcCard = service.create_card(uid=payload.uid, name=payload.name, user_id=payload.user_id)
    return Response(success=True, data=nfcCard, detail="NFC Card successfully created")

# -----------------------------
# Get all NFC cards
# -----------------------------
@router.get("/", response_model=List[NfcCardRead])
def list_nfc_cards(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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
def get_card_by_uid(uid: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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
def get_cards_by_user(user_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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
