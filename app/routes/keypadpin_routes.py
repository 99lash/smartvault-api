from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.KeypadPinsService import KeypadPinsService
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.schemas.Response import Response
from app.schemas.keypad_pin import KeypadPinCreate, KeypadPinAssign, KeypadPinRead
from app.services.users.UserService import UserService
from app.core.dependencies import get_current_admin, get_current_user
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
def create_keypad_pin(payload: KeypadPinCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
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
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
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
        pins = service.get_user_pins(user_id)
    elif vault_id is not None:
        pins = service.get_vault_pins(vault_id)
    else:
        pins = service.list_keypad_pins()

    # Enhance pins with user information for better UI display
    enhanced_pins = []
    user_service = UserService(db)  # Initialize UserService

    for pin in pins:
        pin_dict = pin.__dict__.copy()

        # If PIN has a user_id, fetch user details
        if pin.user_id:
            user = user_service.get_user_by_id(pin.user_id)
            if user:
                pin_dict.update({
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name
                })
            else:
                # User not found, provide null values
                pin_dict.update({
                    'username': None,
                    'first_name': None,
                    'last_name': None
                })
        else:
            # No user assigned to PIN
            pin_dict.update({
                'username': None,
                'first_name': None,
                'last_name': None
            })

        enhanced_pins.append(pin_dict)

    return enhanced_pins


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
def get_keypad_pin(pin_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Fetch a single keypad pin by ID.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_id(pin_id)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")

    # Enhance pin with user information for better UI display
    pin_dict = pin.__dict__.copy()

    # If PIN has a user_id, fetch user details
    if pin.user_id:
        user_service = UserService(db)  # Initialize UserService
        user = user_service.get_user_by_id(pin.user_id)
        if user:
            pin_dict.update({
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        else:
            # User not found, provide null values
            pin_dict.update({
                'username': None,
                'first_name': None,
                'last_name': None
            })
    else:
        # No user assigned to PIN
        pin_dict.update({
            'username': None,
            'first_name': None,
            'last_name': None
        })

    return pin_dict


# -----------------------------
# Get a keypad pin by pin code
# -----------------------------
@router.get("/pin/{pin_code}", response_model=KeypadPinRead)
def get_keypad_pin_by_pin(pin_code: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Fetch a keypad pin by its pin code.
    - Raises 404 if not found.
    """
    service = KeypadPinsService(db)
    pin = service.get_keypad_pin_by_pin(pin_code)
    if not pin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keypad Pin not found")

    # Enhance pin with user information for better UI display
    pin_dict = pin.__dict__.copy()

    # If PIN has a user_id, fetch user details
    if pin.user_id:
        user_service = UserService(db)  # Initialize UserService
        user = user_service.get_user_by_id(pin.user_id)
        if user:
            pin_dict.update({
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            })
        else:
            # User not found, provide null values
            pin_dict.update({
                'username': None,
                'first_name': None,
                'last_name': None
            })
    else:
        # No user assigned to PIN
        pin_dict.update({
            'username': None,
            'first_name': None,
            'last_name': None
        })

    return pin_dict


# -----------------------------
# Assign a keypad pin to a user
# -----------------------------
@router.patch("/{pin_id}/assign", response_model=Response)
def assign_keypad_pin_to_user(pin_id: int, payload: KeypadPinAssign, db: Session = Depends(get_db), current_user = Depends(get_current_admin)):
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
def delete_keypad_pin(
    pin_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Deletes a keypad pin by ID.

    Authorization:
    - User must be an admin of the vault that the PIN belongs to
    - System-wide admin role is not required

    Raises:
    - 404: If PIN not found
    - 403: If user lacks vault admin permissions
    - 500: If deletion fails unexpectedly
    """
    try:
        # First get the PIN to find which vault it belongs to
        keypad_service = KeypadPinsService(db)
        pin = keypad_service.get_keypad_pin_by_id(pin_id)

        if not pin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Keypad Pin not found"
            )

        # Check if user is admin of the vault that this PIN belongs to
        membership_service = VaultMembershipService(db)
        if not membership_service.is_user_admin_of_vault(current_user.id, pin.vault_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access to the vault required to delete PINs"
            )

        # Proceed with deletion
        deleted_pin = keypad_service.delete_keypad_pin(pin_id)
        if not deleted_pin:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete PIN"
            )

        return Response(
            success=True,
            detail=f"Keypad Pin {pin_id} deleted successfully"
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while deleting PIN: {str(e)}"
        )