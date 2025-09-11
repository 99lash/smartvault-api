from sqlalchemy.orm import Session
from app.models.KeypadPins import KeypadPins  # adjust import path if needed
from .Repository import Repository  # your base Repository

class KeypadPinsRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, KeypadPins)

    def get_by_pin_code(self, pin_code: str):
        """Fetch a keypad pin by its pin code"""
        return self.db.query(self.model).filter(self.model.pin_code == pin_code).first()

    def get_by_user_id(self, user_id: int):
        """Fetch all keypad pins for a specific user"""
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()
