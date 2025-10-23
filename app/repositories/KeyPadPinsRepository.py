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

    def get_by_user_and_pin(self, user_id: int, pin_code: str):
        """Fetch a specific pin for a specific user"""
        return self.db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.pin_code == pin_code
        ).first()

    def get_by_user_vault_and_pin(self, user_id: int, vault_id: int, pin_code: str):
        """Fetch a specific pin for a specific user within a specific vault"""
        return self.db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.vault_id == vault_id,
            self.model.pin_code == pin_code
        ).first()

    def get_by_vault_id(self, vault_id: int):
        """Fetch all keypad pins for a specific vault"""
        return self.db.query(self.model).filter(self.model.vault_id == vault_id).all()
    
    def get_by_user_and_vault(self, user_id: int, vault_id: int):
        """Fetch all keypad pins for a specific user in a specific vault"""
        return self.db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.vault_id == vault_id
        ).all()
    
    def get_by_vault_and_role_filter(self, vault_id: int, user_id: int, is_admin: bool):
        """
        Fetch keypad pins for a vault with role-based filtering.
        
        Args:
            vault_id (int): ID of the vault
            user_id (int): ID of the requesting user
            is_admin (bool): Whether the user is an admin of the vault
            
        Returns:
            List[KeypadPins]: Filtered pins based on user role
        """
        if is_admin:
            # Admins can see all pins in the vault
            return self.get_by_vault_id(vault_id)
        else:
            # Members can only see their own pins in the vault
            return self.get_by_user_and_vault(user_id, vault_id)

    def hard_delete(self, pin_id: int) -> bool:
        """
        Permanently delete a keypad pin from the database.

        Args:
            pin_id (int): ID of the keypad pin to delete

        Returns:
            bool: True if pin was deleted, False if not found
        """
        pin = self.db.query(self.model).filter(self.model.id == pin_id).first()
        if pin:
            self.db.delete(pin)
            self.db.commit()
            return True
        return False
