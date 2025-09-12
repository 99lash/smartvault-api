from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.services.NfcCardService import NfcCardService
from app.schemas.NfcCardCreate import NfcCardCreate
from app.schemas.NfcCardResponse import NfcCardResponse

router = APIRouter(prefix="/nfc-cards", tags=["NFC Cards"])

# -----------------------------
# Create a new NFC card
# -----------------------------
@router.post("/", response_model=NfcCardResponse)
def create_nfc_card(card_data: NfcCardCreate, db: Session = Depends(get_db)):
    service = NfcCardService(db)
    return service.create_card(uid=card_data.uid, user_id=card_data.user_id)

# -----------------------------
# Get all NFC cards
# -----------------------------
@router.get("/", response_model=List[NfcCardResponse])
def list_nfc_cards(db: Session = Depends(get_db)):
    service = NfcCardService(db)
    return service.get_all_cards()

# -----------------------------
# Get NFC card by UID
# -----------------------------
@router.get("/uid/{uid}", response_model=NfcCardResponse)
def get_card_by_uid(uid: str, db: Session = Depends(get_db)):
    service = NfcCardService(db)
    card = service.get_card_by_uid(uid)
    if not card:
        raise HTTPException(status_code=404, detail="NFC card not found")
    return card

# -----------------------------
# Get all cards assigned to a user
# -----------------------------
@router.get("/user/{user_id}", response_model=List[NfcCardResponse])
def get_cards_by_user(user_id: int, db: Session = Depends(get_db)):
    service = NfcCardService(db)
    return service.get_cards_by_user(user_id)

# -----------------------------
# Assign card to user
# -----------------------------
@router.patch("/{card_id}/assign", response_model=NfcCardResponse)
def assign_card_to_user(card_id: int, user_id: int, db: Session = Depends(get_db)):
    service = NfcCardService(db)
    card = service.assign_card_to_user(card_id, user_id)
    if not card:
        raise HTTPException(status_code=404, detail="NFC card not found")
    return card

# -----------------------------
# Soft delete a NFC card
# -----------------------------
@router.delete("/{card_id}", response_model=NfcCardResponse)
def delete_nfc_card(card_id: int, db: Session = Depends(get_db)):
    service = NfcCardService(db)
    card = service.delete_card(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="NFC card not found")
    return card
