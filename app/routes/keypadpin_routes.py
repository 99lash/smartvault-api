from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    - Pin code must be unique within the user's pins within the same vault.
    - Different users can have the same pin code in different vaults.
    - user_id is optional (can be None if unassigned).
    - vault_id is required to associate the pin with a specific vault.
    """
    try:
        service = KeypadPinsService(db)
        pin = service.create_keypad_pin(payload.pin_code, payload.vault_id, payload.user_id)
        return Response(success=True, data=pin, detail="Pin created successfully")
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )


# -----------------------------
# List all keypad pins with optional filtering
# -----------------------------
@router.get("/", response_model=list[KeypadPinRead])
def list_keypad_pins(
    user_id: int | None = Query(None, description="Filter pins by user ID"),
    vault_id: int | None = Query(None, description="Filter pins by vault ID"),
    db: Session = Depends(get_db)
):
    """
    Returns keypad pins with optional filtering.

    Query Parameters:
    - user_id: Filter pins by specific user ID (mutually exclusive with vault_id)
    - vault_id: Filter pins by vault ID (mutually exclusive with user_id)

    Note: Provide either user_id OR vault_id, but not both.
    If no filters are provided, returns all pins.
    """
    # Manual validation for parameter constraints
    if user_id is not None and user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must be greater than 0"
        )

    if vault_id is not None and vault_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vault_id must be greater than 0"
        )

    # Validate that only one filter is provided
    if user_id is not None and vault_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either user_id or vault_id, but not both"
        )

    service = KeypadPinsService(db)

    # Apply filters based on provided parameters
    if user_id is not None:
        return service.get_user_pins(user_id)
    elif vault_id is not None:
        return service.get_vault_pins(vault_id)
    else:
        return service.list_keypad_pins()


# -----------------------------
# Get keypad pins by vault ID
# -----------------------------
@router.get("/vault/{vault_id}", response_model=list[KeypadPinRead])
def get_keypad_pins_by_vault(vault_id: int, db: Session = Depends(get_db)):
    """
    Returns all keypad pins for a specific vault.
    - Raises 404 if vault has no pins.
    """
    service = KeypadPinsService(db)
    pins = service.get_vault_pins(vault_id)
    return pins


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