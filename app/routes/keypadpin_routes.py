from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.KeypadPinsService import KeypadPinsService
from app.schemas.Response import Response
from app.schemas.keypad_pin import KeypadPinCreate, KeypadPinAssign, KeypadPinRead
from app.services.users.UserService import UserService
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
@router.post("/", response_model=Response[KeypadPinRead], status_code=status.HTTP_201_CREATED)
def create_keypad_pin(payload: KeypadPinCreate, db: Session = Depends(get_db)):
    """
    Creates a new keypad pin record.
    - Pin code must be unique within the user's pins.
    - Different users can have the same pin code.
    - user_id is optional (can be None if unassigned).
    """
    try:
        service = KeypadPinsService(db)
        pin = service.create_keypad_pin(payload.pin_code, payload.user_id)
        return Response(success=True, data=pin, detail="Pin created successfully")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


# -----------------------------
# List all keypad pins
# -----------------------------
@router.get("/", response_model=list[KeypadPinRead])
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
@router.get("/{pin_id}", response_model=KeypadPinRead)
def get_keypad_pin(pin_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single keypad pin by ID.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_id(pin_id)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")
    return pin


# -----------------------------
# Get a keypad pin by pin code
# -----------------------------
@router.get("/pin/{pin_code}", response_model=KeypadPinRead)
def get_keypad_pin_by_pin(pin_code: str, db: Session = Depends(get_db)):
    """
    Fetch a keypad pin by its pin code.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_pin(pin_code)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")
    return pin


# -----------------------------
# Assign a keypad pin to a user
# -----------------------------
@router.patch("/{pin_id}/assign", response_model=Response)
def assign_keypad_pin_to_user(pin_id: int, payload: KeypadPinAssign, db: Session = Depends(get_db)):
    """
    Assigns an existing keypad pin to a user.
    - Updates the `user_id` field.
    - Raises 404 if pin or user not found.
    """
    userService = UserService(db)
    user = userService.get_user_by_id(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    keypadPinService = KeypadPinsService(db)
    pin = keypadPinService.assign_to_user(pin_id, payload.user_id)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")

    return Response(success=True, detail=f"Keypad Pin {pin_id} assigned to user {payload.user_id}")


# -----------------------------
# Delete a keypad pin
# -----------------------------
@router.delete("/{pin_id}", response_model=Response)
def delete_keypad_pin(pin_id: int, db: Session = Depends(get_db)):
    """
    Deletes a keypad pin by ID.
    - Soft deletes if the model has a deleted_at column.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.delete_keypad_pin(pin_id)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")
    return Response(success=True, detail=f"Keypad Pin {pin_id} deleted successfully")