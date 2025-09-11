from sqlalchemy.orm import Session
from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
from app.models.KeypadPins import KeypadPins


# -----------------------------
# Service layer for KeypadPins logic
# -----------------------------
# Encapsulates business logic related to keypad pins:
# - DB operations through KeypadPinsRepository
# - NFC UID lookups
class KeypadPinsService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = KeypadPinsRepository(db)

    # Create a new keypad pin
    def create_keypad_pin(self, pin_code: str, user_id: int | None = None) -> KeypadPins:
        return self.repo.create(pin_code=pin_code, user_id=user_id)

    # Fetch a keypad pin by ID
    def get_keypad_pin_by_id(self, pin_id: int) -> KeypadPins | None:
        return self.repo.get_by_id(pin_id)

    # Fetch a keypad pin by pin code
    def get_keypad_pin_by_pin(self, pin_code: str) -> KeypadPins | None:
        return self.repo.get_by_pin_code(pin_code)

    # Fetch all keypad pins
    def list_keypad_pins(self) -> list[KeypadPins]:
        return self.repo.get_all()

    # Delete a keypad pin by ID (soft if model supports deleted_at)
    def delete_keypad_pin(self, pin_id: int) -> KeypadPins | None:
        return self.repo.delete(pin_id)

    # Optional: assign a keypad pin to a user
    def assign_to_user(self, pin_id: int, user_id: int) -> KeypadPins | None:
        return self.repo.update(pin_id, user_id=user_id)
