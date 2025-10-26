"""
NFC Card Access Control Service

Handles role-based access control for NFC card operations following SOC principles.
Separates authorization logic from business logic and route handlers.
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
from fastapi import HTTPException, status
from app.models.NfcCard import NfcCard
from app.models.VaultMembership import MembershipRole
from app.services.VaultAccessControlService import VaultAccessControlService
from app.services.NfcCardService import NfcCardService


class NfcCardAccessControlService:
    """
    Service for managing NFC card access control and authorization.
    
    Follows SOC: Separates authorization concerns from business logic.
    Provides centralized access control for NFC card operations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with database session.
        
        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db
        self.vault_access_control = VaultAccessControlService(db)
        self.nfc_service = NfcCardService(db)
    
    def get_authorized_cards_for_user(
        self, 
        user_id: int, 
        vault_id: Optional[int] = None,
        target_user_id: Optional[int] = None
    ) -> List[NfcCard]:
        """
        Get NFC cards that the user is authorized to view based on their role.
        
        Args:
            user_id (int): ID of the requesting user
            vault_id (Optional[int]): Specific vault ID to filter by
            target_user_id (Optional[int]): Specific user ID to filter by
            
        Returns:
            List[NfcCard]: Authorized NFC cards for the user
            
        Raises:
            HTTPException: If user lacks permission
        """
        # If requesting specific user's cards, validate access
        if target_user_id is not None:
            return self._get_user_cards_with_authorization(user_id, target_user_id, vault_id)
        
        # If requesting vault cards, validate vault membership
        if vault_id is not None:
            return self._get_vault_cards_with_authorization(user_id, vault_id)
        
        # If no filters, return user's own cards
        return self.nfc_service.get_cards_by_user(user_id)
    
    def _get_user_cards_with_authorization(
        self, 
        requesting_user_id: int, 
        target_user_id: int,
        vault_id: Optional[int] = None
    ) -> List[NfcCard]:
        """
        Get user's NFC cards with proper authorization checks.
        
        Args:
            requesting_user_id (int): ID of the user making the request
            target_user_id (int): ID of the user whose cards are requested
            vault_id (Optional[int]): Specific vault ID to filter by
            
        Returns:
            List[NfcCard]: Authorized NFC cards
            
        Raises:
            HTTPException: If user lacks permission
        """
        # Users can only view their own cards unless they're admin
        if requesting_user_id != target_user_id:
            # Check if requesting user is admin of any vault that contains target user's cards
            if not self._is_admin_of_user_cards_vaults(requesting_user_id, target_user_id, vault_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own NFC cards"
                )
        
        # Get target user's cards
        user_cards = self.nfc_service.get_cards_by_user(target_user_id)
        
        # Filter by vault if specified
        if vault_id is not None:
            user_cards = [card for card in user_cards if card.vault_id == vault_id]
        
        return user_cards
    
    def _get_vault_cards_with_authorization(
        self, 
        user_id: int, 
        vault_id: int
    ) -> List[NfcCard]:
        """
        Get vault NFC cards with proper authorization checks.
        
        Args:
            user_id (int): ID of the requesting user
            vault_id (int): ID of the vault
            
        Returns:
            List[NfcCard]: Authorized NFC cards for the vault
            
        Raises:
            HTTPException: If user lacks permission
        """
        # Check vault membership and get user role
        is_member, role = self.vault_access_control.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not a member of this vault"
            )
        
        # Apply role-based filtering
        if role == MembershipRole.member:
            # Members can only see their own cards in this vault
            user_cards = self.nfc_service.get_cards_by_user(user_id)
            return [card for card in user_cards if card.vault_id == vault_id]
        
        elif role == MembershipRole.admin:
            # Admins can see all cards in the vault
            return self.nfc_service.get_cards_by_vault(vault_id)
        
        else:  # guest
            # Guests cannot see any cards
            return []
    
    def _is_admin_of_user_cards_vaults(
        self, 
        requesting_user_id: int, 
        target_user_id: int,
        vault_id: Optional[int] = None
    ) -> bool:
        """
        Check if requesting user is admin of vaults containing target user's NFC cards.
        
        Args:
            requesting_user_id (int): ID of the requesting user
            target_user_id (int): ID of the target user
            vault_id (Optional[int]): Specific vault ID to check
            
        Returns:
            bool: True if user is admin of relevant vaults
        """
        # Get target user's cards
        target_cards = self.nfc_service.get_cards_by_user(target_user_id)
        
        # Filter by vault if specified
        if vault_id is not None:
            target_cards = [card for card in target_cards if card.vault_id == vault_id]
        
        # Check if requesting user is admin of any vault containing target user's cards
        for card in target_cards:
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                requesting_user_id, card.vault_id
            )
            if is_member and role == MembershipRole.admin:
                return True
        
        return False
    
    def can_user_view_card(
        self, 
        user_id: int, 
        card_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user can view a specific NFC card.
        
        Args:
            user_id (int): ID of the requesting user
            card_id (int): ID of the NFC card
            
        Returns:
            Tuple[bool, Optional[str]]: (can_view, reason)
        """
        try:
            card = self.nfc_service.get_card_by_id(card_id)
            if not card:
                return False, "NFC card not found"
            
            # Check if user owns the card
            if card.user_id == user_id:
                return True, "User owns this NFC card"
            
            # Check if user is admin of the vault containing this card
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                user_id, card.vault_id
            )
            
            if is_member and role == MembershipRole.admin:
                return True, "User is admin of the vault"
            
            return False, "User lacks permission to view this NFC card"
            
        except Exception as e:
            return False, f"Error checking NFC card access: {str(e)}"
    
    def can_user_assign_card(self, user_id: int, card_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user can assign a specific NFC card.

        Args:
            user_id (int): ID of the requesting user
            card_id (int): ID of the NFC card

        Returns:
            Tuple[bool, Optional[str]]: (can_assign, reason)
        """
        try:
            card = self.nfc_service.get_card_by_id(card_id)
            if not card:
                return False, "NFC card not found"

            # Check if user is admin of the vault containing this card
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                user_id, card.vault_id
            )

            if not is_member:
                return False, "User is not a member of the vault containing this card"

            if role != MembershipRole.admin:
                return False, "Vault admin access required to assign NFC cards"

            return True, "User is admin of the vault"

        except Exception as e:
            return False, f"Error checking NFC card assignment access: {str(e)}"

    def can_user_delete_card(self, user_id: int, card_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user can delete a specific NFC card.

        Args:
            user_id (int): ID of the requesting user
            card_id (int): ID of the NFC card

        Returns:
            Tuple[bool, Optional[str]]: (can_delete, reason)
        """
        try:
            card = self.nfc_service.get_card_by_id(card_id)
            if not card:
                return False, "NFC card not found"

            # Check if user is admin of the vault containing this card
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                user_id, card.vault_id
            )

            if not is_member:
                return False, "User is not a member of the vault containing this card"

            if role != MembershipRole.admin:
                return False, "Vault admin access required to delete NFC cards"

            return True, "User is admin of the vault"

        except Exception as e:
            return False, f"Error checking NFC card deletion access: {str(e)}"

    def get_user_card_permissions(self, user_id: int, vault_id: int) -> dict:
        """
        Get comprehensive NFC card permissions for a user in a vault.

        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault

        Returns:
            dict: Permission details
        """
        is_member, role = self.vault_access_control.check_vault_access_and_role(user_id, vault_id)

        if not is_member:
            return {
                "can_view_own_cards": False,
                "can_view_all_cards": False,
                "can_create_cards": False,
                "can_delete_cards": False,
                "role": None,
                "reason": "User is not a member of this vault"
            }

        permissions = {
            "can_view_own_cards": True,
            "can_view_all_cards": role == MembershipRole.admin,
            "can_create_cards": role in [MembershipRole.admin, MembershipRole.member],
            "can_delete_cards": role == MembershipRole.admin,
            "role": role.value if role else None,
            "reason": "Access granted"
        }

        return permissions