from sqlalchemy.orm import Session
from typing import Optional, Tuple
from fastapi import HTTPException, status
from app.models.VaultMembership import MembershipRole
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.services.NfcCardService import NfcCardService
from app.services.KeypadPinsService import KeypadPinsService


class VaultAccessControlService:
    """
    Service for managing role-based access control and limits for vault operations.
    
    This service enforces business rules based on user roles:
    - MEMBER: Limited to 1 NFC card and 1 keypad pin per vault (auto-assigned to themselves)
    - ADMIN: No limits on NFC cards and keypad pins (can assign to any vault member or leave unassigned)
    - GUEST: No creation permissions (read-only access)
    
    The service provides centralized access control logic that can be used across
    different route handlers to ensure consistent enforcement of business rules.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with a database session.
        
        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db
        self.membership_service = VaultMembershipService(db)
        self.nfc_service = NfcCardService(db)
        self.keypad_service = KeypadPinsService(db)
    
    def check_vault_access_and_role(self, user_id: int, vault_id: int) -> Tuple[bool, Optional[MembershipRole]]:
        """
        Check if user is a member of the vault and get their role.
        
        Args:
            user_id (int): ID of the user to check
            vault_id (int): ID of the vault to check
            
        Returns:
            Tuple[bool, Optional[MembershipRole]]: (is_member, role)
                - is_member: True if user is a member of the vault
                - role: User's role in the vault (None if not a member)
        """
        role = self.membership_service.get_user_role_in_vault(user_id, vault_id)
        is_member = role is not None
        return is_member, role
    
    def can_create_nfc_card(self, user_id: int, vault_id: int) -> Tuple[bool, str]:
        """
        Check if user can create an NFC card based on their role and current count.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Returns:
            Tuple[bool, str]: (can_create, reason)
                - can_create: True if user can create an NFC card
                - reason: Human-readable explanation of the decision
        """
        is_member, role = self.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            return False, "User is not a member of this vault"
        
        if role == MembershipRole.guest:
            return False, "Guest users cannot create NFC cards"
        
        if role == MembershipRole.admin:
            return True, "Admin users have unlimited NFC cards"
        
        if role == MembershipRole.member:
            # Check current NFC card count for this user in this vault
            user_nfc_cards = self.nfc_service.get_cards_by_user(user_id)
            vault_nfc_cards = [card for card in user_nfc_cards if card.vault_id == vault_id]
            
            if len(vault_nfc_cards) >= 1:
                return False, "Members are limited to 1 NFC card per vault"
            
            return True, "Member can create NFC card"
        
        return False, f"Role '{role}' not allowed to create NFC cards"
    
    def can_create_keypad_pin(self, user_id: int, vault_id: int) -> Tuple[bool, str]:
        """
        Check if user can create a keypad pin based on their role and current count.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Returns:
            Tuple[bool, str]: (can_create, reason)
                - can_create: True if user can create a keypad pin
                - reason: Human-readable explanation of the decision
        """
        is_member, role = self.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            return False, "User is not a member of this vault"
        
        if role == MembershipRole.guest:
            return False, "Guest users cannot create keypad pins"
        
        if role == MembershipRole.admin:
            return True, "Admin users have unlimited keypad pins"
        
        if role == MembershipRole.member:
            # Check current keypad pin count for this user in this vault
            user_pins = self.keypad_service.get_user_pins(user_id)
            vault_pins = [pin for pin in user_pins if pin.vault_id == vault_id]
            
            if len(vault_pins) >= 1:
                return False, "Members are limited to 1 keypad pin per vault"
            
            return True, "Member can create keypad pin"
        
        return False, f"Role '{role}' not allowed to create keypad pins"
    
    def enforce_nfc_card_limit(self, user_id: int, vault_id: int) -> None:
        """
        Enforce NFC card creation limits. Raises HTTPException if limit exceeded.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Raises:
            HTTPException: If user cannot create NFC card
        """
        can_create, reason = self.can_create_nfc_card(user_id, vault_id)
        if not can_create:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=reason
            )
    
    def enforce_keypad_pin_limit(self, user_id: int, vault_id: int) -> None:
        """
        Enforce keypad pin creation limits. Raises HTTPException if limit exceeded.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Raises:
            HTTPException: If user cannot create keypad pin
        """
        can_create, reason = self.can_create_keypad_pin(user_id, vault_id)
        if not can_create:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=reason
            )
    
    def get_user_limits_info(self, user_id: int, vault_id: int) -> dict:
        """
        Get comprehensive information about user's limits and current counts in a vault.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Returns:
            dict: Information about user's role, limits, and current counts
        """
        is_member, role = self.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            return {
                "is_member": False,
                "role": None,
                "nfc_cards": {"current_count": 0, "limit": None, "can_create": False},
                "keypad_pins": {"current_count": 0, "limit": None, "can_create": False}
            }
        
        # Get current counts
        user_nfc_cards = self.nfc_service.get_cards_by_user(user_id)
        vault_nfc_cards = [card for card in user_nfc_cards if card.vault_id == vault_id]
        
        user_pins = self.keypad_service.get_user_pins(user_id)
        vault_pins = [pin for pin in user_pins if pin.vault_id == vault_id]
        
        # Determine limits based on role
        nfc_limit = None if role == MembershipRole.admin else 1
        keypad_limit = None if role == MembershipRole.admin else 1
        
        # Check if user can create
        nfc_can_create, _ = self.can_create_nfc_card(user_id, vault_id)
        keypad_can_create, _ = self.can_create_keypad_pin(user_id, vault_id)
        
        return {
            "is_member": True,
            "role": role.value if role else None,
            "nfc_cards": {
                "current_count": len(vault_nfc_cards),
                "limit": nfc_limit,
                "can_create": nfc_can_create
            },
            "keypad_pins": {
                "current_count": len(vault_pins),
                "limit": keypad_limit,
                "can_create": keypad_can_create
            }
        }
    
    def should_auto_assign_to_user(self, user_id: int, vault_id: int) -> bool:
        """
        Determine if a resource should be automatically assigned to the user.
        
        Members should have resources auto-assigned to themselves.
        Admins can choose to assign or leave unassigned.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Returns:
            bool: True if resource should be auto-assigned to user
        """
        is_member, role = self.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            return False
        
        # Members should have resources auto-assigned to themselves
        if role == MembershipRole.member:
            return True
        
        # Admins can choose, so don't auto-assign
        if role == MembershipRole.admin:
            return False
        
        # Guests can't create resources
        return False
