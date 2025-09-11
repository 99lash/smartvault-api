from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.keypadpin_mngment_service  import KeypadPinsService

# -----------------------------
# FastAPI router for KeypadPins endpoints
# -----------------------------
# Handles all HTTP requests related to keypad pins:
# - create
# - list
# - fetch by ID
# - fetch by NFC UID
# - assign to user
# - delete (soft if supported)
router = APIRouter(prefix="/keypad-pins", tags=["keypad_pins"])


# -----------------------------
# Create a new keypad pin
# -----------------------------
@router.post("/")
def create_keypad_pin(pin_code: str, user_id: int | None = None, db: Session = Depends(get_db)):
    """
    Creates a new keypad pin record.
    - Requires a pin code (must be unique).
    - user_id is optional (can be None if unassigned).
    """
    service = KeypadPinsService(db)
    pin = service.create_keypad_pin(pin_code=pin_code, user_id=user_id)
    return pin


# -----------------------------
# List all keypad pins
# -----------------------------
@router.get("/")
def list_keypad_pins(db: Session = Depends(get_db)):
    """
    Returns all keypad pins.
    - Could later exclude soft-deleted records.
    """
    service = KeypadPinsService(db)
    return service.list_keypad_pins()


# -----------------------------
# Get a keypad pin by ID
# -----------------------------
@router.get("/{pin_id}")
def get_keypad_pin(pin_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single keypad pin by ID.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_id(pin_id)
    if not pin:
        raise HTTPException(status_code=404, detail="KeypadPin not found")
    return pin


# -----------------------------
# Get a keypad pin by pin code
# -----------------------------
@router.get("/pin/{pin_code}")
def get_keypad_pin_by_pin(pin_code: str, db: Session = Depends(get_db)):
    """
    Fetch a keypad pin by its pin code.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_pin(pin_code)
    if not pin:
        raise HTTPException(status_code=404, detail="KeypadPin not found")
    return pin


# -----------------------------
# Assign a keypad pin to a user
# -----------------------------
@router.patch("/{pin_id}/assign")
def assign_keypad_pin_to_user(pin_id: int, user_id: int, db: Session = Depends(get_db)):
    """
    Assigns an existing keypad pin to a user.
    - Updates the `user_id` field.
    - Raises 404 if pin not found.
    """
    service = KeypadPinsService(db)
    pin = service.assign_to_user(pin_id, user_id)
    if not pin:
        raise HTTPException(status_code=404, detail="KeypadPin not found")
    return {"message": f"KeypadPin {pin_id} assigned to user {user_id}"}


# -----------------------------
# Delete a keypad pin
# -----------------------------
@router.delete("/{pin_id}")
def delete_keypad_pin(pin_id: int, db: Session = Depends(get_db)):
    """
    Deletes a keypad pin by ID.
    - Soft deletes if the model has a deleted_at column.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.delete_keypad_pin(pin_id)
    if not pin:
        raise HTTPException(status_code=404, detail="KeypadPin not found")
    return {"message": f"KeypadPin {pin_id} deleted successfully"}
