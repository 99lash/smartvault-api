from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
from app.models.KeypadPins import KeypadPins


# -----------------------------
# Service layer for KeypadPins logic
# -----------------------------
# Encapsulates business logic related to keypad pins:
# - DB operations through KeypadPinsRepository
# - Pin code uniqueness within same user
class KeypadPinsService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.db = db
        self.repo = KeypadPinsRepository(db)

    # Create a new keypad pin
    def create_keypad_pin(self, pin_code: str, vault_id: int, user_id: int | None = None) -> KeypadPins:
        # Check if user already has this pin code within the same vault (only if user_id is provided)
        if user_id:
            existing_pin = self.repo.get_by_user_vault_and_pin(user_id, vault_id, pin_code)
            if existing_pin:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User {user_id} already has pin code '{pin_code}' in vault {vault_id}"
                )

        try:
            return self.repo.create(pin_code=pin_code, vault_id=vault_id, user_id=user_id)
        except IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                # Handle composite unique constraint violation
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Pin code '{pin_code}' already exists for this user"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An error occurred while creating the pin"
            )

    # Fetch a keypad pin by ID
    def get_keypad_pin_by_id(self, pin_id: int) -> KeypadPins | None:
        return self.repo.get_by_id(pin_id)

    # Fetch a keypad pin by pin code (returns all users with this pin)
    def get_keypad_pin_by_pin(self, pin_code: str) -> list[KeypadPins]:
        return self.repo.get_by_pin_code(pin_code)

    # Fetch all keypad pins
    def list_keypad_pins(self) -> list[KeypadPins]:
        return self.repo.get_all()

    # Delete a keypad pin by ID (soft if model supports deleted_at)
    def delete_keypad_pin(self, pin_id: int) -> KeypadPins | None:
        return self.repo.delete(pin_id)

    # Assign a keypad pin to a user
    def assign_to_user(self, pin_id: int, user_id: int) -> KeypadPins | None:
        # Check if the user already has this pin
        pin = self.repo.get_by_id(pin_id)
        if not pin:
            return None

        existing_pin = self.repo.get_by_user_and_pin(user_id, pin.pin_code)
        if existing_pin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User {user_id} already has pin code '{pin.pin_code}'"
            )

        return self.repo.update(pin_id, user_id=user_id)

    # Get all pins for a specific user
    def get_user_pins(self, user_id: int) -> list[KeypadPins]:
        """Get all pins for a specific user"""
        return self.repo.get_by_user_id(user_id)

    # Get all pins for a specific vault
    def get_vault_pins(self, vault_id: int) -> list[KeypadPins]:
        """Get all pins for a specific vault"""
        return self.repo.get_by_vault_id(vault_id)
