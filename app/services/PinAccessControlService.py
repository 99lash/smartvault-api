"""
PIN Access Control Service

Handles role-based access control for PIN operations following SOC principles.
Separates authorization logic from business logic and route handlers.
"""

from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
from fastapi import HTTPException, status
from app.models.KeypadPins import KeypadPins
from app.models.VaultMembership import MembershipRole
from app.services.VaultAccessControlService import VaultAccessControlService
from app.services.KeypadPinsService import KeypadPinsService


class PinAccessControlService:
    """
    Service for managing PIN access control and authorization.
    
    Follows SOC: Separates authorization concerns from business logic.
    Provides centralized access control for PIN operations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the service with database session.
        
        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db
        self.vault_access_control = VaultAccessControlService(db)
        self.pin_service = KeypadPinsService(db)
    
    def get_authorized_pins_for_user(
        self, 
        user_id: int, 
        vault_id: Optional[int] = None,
        target_user_id: Optional[int] = None
    ) -> List[KeypadPins]:
        """
        Get PINs that the user is authorized to view based on their role.
        
        Args:
            user_id (int): ID of the requesting user
            vault_id (Optional[int]): Specific vault ID to filter by
            target_user_id (Optional[int]): Specific user ID to filter by
            
        Returns:
            List[KeypadPins]: Authorized PINs for the user
            
        Raises:
            HTTPException: If user lacks permission
        """
        # If requesting specific user's PINs, validate access
        if target_user_id is not None:
            return self._get_user_pins_with_authorization(user_id, target_user_id, vault_id)
        
        # If requesting vault PINs, validate vault membership
        if vault_id is not None:
            return self._get_vault_pins_with_authorization(user_id, vault_id)
        
        # If no filters, return user's own PINs
        return self.pin_service.get_user_pins(user_id)
    
    def _get_user_pins_with_authorization(
        self, 
        requesting_user_id: int, 
        target_user_id: int,
        vault_id: Optional[int] = None
    ) -> List[KeypadPins]:
        """
        Get user's PINs with proper authorization checks.
        
        Args:
            requesting_user_id (int): ID of the user making the request
            target_user_id (int): ID of the user whose PINs are requested
            vault_id (Optional[int]): Specific vault ID to filter by
            
        Returns:
            List[KeypadPins]: Authorized PINs
            
        Raises:
            HTTPException: If user lacks permission
        """
        # Users can only view their own PINs unless they're admin
        if requesting_user_id != target_user_id:
            # Check if requesting user is admin of any vault that contains target user's PINs
            if not self._is_admin_of_user_pins_vaults(requesting_user_id, target_user_id, vault_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only view your own PINs"
                )
        
        # Get target user's PINs
        user_pins = self.pin_service.get_user_pins(target_user_id)
        
        # Filter by vault if specified
        if vault_id is not None:
            user_pins = [pin for pin in user_pins if pin.vault_id == vault_id]
        
        return user_pins
    
    def _get_vault_pins_with_authorization(
        self, 
        user_id: int, 
        vault_id: int
    ) -> List[KeypadPins]:
        """
        Get vault PINs with proper authorization checks.
        
        Args:
            user_id (int): ID of the requesting user
            vault_id (int): ID of the vault
            
        Returns:
            List[KeypadPins]: Authorized PINs for the vault
            
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
            # Members can only see their own pins in this vault
            user_pins = self.pin_service.get_user_pins(user_id)
            return [pin for pin in user_pins if pin.vault_id == vault_id]
        
        elif role == MembershipRole.admin:
            # Admins can see all pins in the vault
            return self.pin_service.get_vault_pins(vault_id)
        
        else:  # guest
            # Guests cannot see any pins
            return []
    
    def _is_admin_of_user_pins_vaults(
        self, 
        requesting_user_id: int, 
        target_user_id: int,
        vault_id: Optional[int] = None
    ) -> bool:
        """
        Check if requesting user is admin of vaults containing target user's PINs.
        
        Args:
            requesting_user_id (int): ID of the requesting user
            target_user_id (int): ID of the target user
            vault_id (Optional[int]): Specific vault ID to check
            
        Returns:
            bool: True if user is admin of relevant vaults
        """
        # Get target user's PINs
        target_pins = self.pin_service.get_user_pins(target_user_id)
        
        # Filter by vault if specified
        if vault_id is not None:
            target_pins = [pin for pin in target_pins if pin.vault_id == vault_id]
        
        # Check if requesting user is admin of any vault containing target user's PINs
        for pin in target_pins:
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                requesting_user_id, pin.vault_id
            )
            if is_member and role == MembershipRole.admin:
                return True
        
        return False
    
    def can_user_view_pin(
        self, 
        user_id: int, 
        pin_id: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user can view a specific PIN.
        
        Args:
            user_id (int): ID of the requesting user
            pin_id (int): ID of the PIN
            
        Returns:
            Tuple[bool, Optional[str]]: (can_view, reason)
        """
        try:
            pin = self.pin_service.get_keypad_pin_by_id(pin_id)
            if not pin:
                return False, "PIN not found"
            
            # Check if user owns the PIN
            if pin.user_id == user_id:
                return True, "User owns this PIN"
            
            # Check if user is admin of the vault containing this PIN
            is_member, role = self.vault_access_control.check_vault_access_and_role(
                user_id, pin.vault_id
            )
            
            if is_member and role == MembershipRole.admin:
                return True, "User is admin of the vault"
            
            return False, "User lacks permission to view this PIN"
            
        except Exception as e:
            return False, f"Error checking PIN access: {str(e)}"
    
    def get_user_pin_permissions(self, user_id: int, vault_id: int) -> dict:
        """
        Get comprehensive PIN permissions for a user in a vault.
        
        Args:
            user_id (int): ID of the user
            vault_id (int): ID of the vault
            
        Returns:
            dict: Permission details
        """
        is_member, role = self.vault_access_control.check_vault_access_and_role(user_id, vault_id)
        
        if not is_member:
            return {
                "can_view_own_pins": False,
                "can_view_all_pins": False,
                "can_create_pins": False,
                "can_delete_pins": False,
                "role": None,
                "reason": "User is not a member of this vault"
            }
        
        permissions = {
            "can_view_own_pins": True,
            "can_view_all_pins": role == MembershipRole.admin,
            "can_create_pins": role in [MembershipRole.admin, MembershipRole.member],
            "can_delete_pins": role == MembershipRole.admin,
            "role": role.value if role else None,
            "reason": "Access granted"
        }
        
        return permissions
