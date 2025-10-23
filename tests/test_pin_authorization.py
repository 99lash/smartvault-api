"""
Unit Tests for PIN Authorization Logic

Tests the role-based access control for PIN operations to ensure:
- Members can only view their own PINs
- Admins can view all PINs in their vaults
- Guests cannot view any PINs
- Proper error handling for unauthorized access
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.services.PinAccessControlService import PinAccessControlService
from app.models.VaultMembership import MembershipRole
from app.models.KeypadPins import KeypadPins


class TestPinAccessControlService:
    """Test cases for PIN access control service."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def pin_access_service(self, mock_db):
        """Create PIN access control service with mocked dependencies."""
        with patch('app.services.PinAccessControlService.VaultAccessControlService') as mock_vault_access, \
             patch('app.services.PinAccessControlService.KeypadPinsService') as mock_pin_service:
            
            service = PinAccessControlService(mock_db)
            service.vault_access_control = mock_vault_access.return_value
            service.pin_service = mock_pin_service.return_value
            
            return service
    
    def test_member_can_view_own_pins_in_vault(self, pin_access_service):
        """Test that members can view their own PINs in a vault."""
        # Arrange
        user_id = 1
        vault_id = 123
        mock_pins = [
            Mock(spec=KeypadPins, id=1, user_id=1, vault_id=123, pin_code="1234"),
            Mock(spec=KeypadPins, id=2, user_id=1, vault_id=123, pin_code="5678")
        ]
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.member)
        pin_access_service.pin_service.get_user_pins.return_value = mock_pins
        
        # Act
        result = pin_access_service.get_authorized_pins_for_user(user_id, vault_id)
        
        # Assert
        assert len(result) == 2
        assert all(pin.vault_id == vault_id for pin in result)
        assert all(pin.user_id == user_id for pin in result)
        pin_access_service.vault_access_control.check_vault_access_and_role.assert_called_once_with(user_id, vault_id)
    
    def test_admin_can_view_all_pins_in_vault(self, pin_access_service):
        """Test that admins can view all PINs in a vault."""
        # Arrange
        user_id = 1
        vault_id = 123
        mock_pins = [
            Mock(spec=KeypadPins, id=1, user_id=1, vault_id=123, pin_code="1234"),
            Mock(spec=KeypadPins, id=2, user_id=2, vault_id=123, pin_code="5678"),
            Mock(spec=KeypadPins, id=3, user_id=3, vault_id=123, pin_code="9999")
        ]
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.admin)
        pin_access_service.pin_service.get_vault_pins.return_value = mock_pins
        
        # Act
        result = pin_access_service.get_authorized_pins_for_user(user_id, vault_id)
        
        # Assert
        assert len(result) == 3
        assert all(pin.vault_id == vault_id for pin in result)
        pin_access_service.vault_access_control.check_vault_access_and_role.assert_called_once_with(user_id, vault_id)
    
    def test_guest_cannot_view_any_pins(self, pin_access_service):
        """Test that guests cannot view any PINs."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.guest)
        
        # Act
        result = pin_access_service.get_authorized_pins_for_user(user_id, vault_id)
        
        # Assert
        assert len(result) == 0
        pin_access_service.vault_access_control.check_vault_access_and_role.assert_called_once_with(user_id, vault_id)
    
    def test_non_member_cannot_view_vault_pins(self, pin_access_service):
        """Test that non-members cannot view vault PINs."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (False, None)
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            pin_access_service.get_authorized_pins_for_user(user_id, vault_id)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "User is not a member of this vault" in str(exc_info.value.detail)
    
    def test_user_can_view_own_pins_when_requesting_by_user_id(self, pin_access_service):
        """Test that users can view their own PINs when requesting by user_id."""
        # Arrange
        requesting_user_id = 1
        target_user_id = 1
        vault_id = None
        mock_pins = [
            Mock(spec=KeypadPins, id=1, user_id=1, vault_id=123, pin_code="1234"),
            Mock(spec=KeypadPins, id=2, user_id=1, vault_id=456, pin_code="5678")
        ]
        
        pin_access_service.pin_service.get_user_pins.return_value = mock_pins
        
        # Act
        result = pin_access_service.get_authorized_pins_for_user(
            requesting_user_id, vault_id, target_user_id
        )
        
        # Assert
        assert len(result) == 2
        assert all(pin.user_id == target_user_id for pin in result)
        pin_access_service.pin_service.get_user_pins.assert_called_once_with(target_user_id)
    
    def test_user_cannot_view_other_users_pins(self, pin_access_service):
        """Test that users cannot view other users' PINs."""
        # Arrange
        requesting_user_id = 1
        target_user_id = 2
        vault_id = None
        
        # Mock that requesting user is not admin of any vault containing target user's PINs
        pin_access_service._is_admin_of_user_pins_vaults.return_value = False
        
        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            pin_access_service.get_authorized_pins_for_user(
                requesting_user_id, vault_id, target_user_id
            )
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "You can only view your own PINs" in str(exc_info.value.detail)
    
    def test_admin_can_view_other_users_pins(self, pin_access_service):
        """Test that admins can view other users' PINs."""
        # Arrange
        requesting_user_id = 1
        target_user_id = 2
        vault_id = None
        mock_pins = [
            Mock(spec=KeypadPins, id=1, user_id=2, vault_id=123, pin_code="1234")
        ]
        
        pin_access_service._is_admin_of_user_pins_vaults.return_value = True
        pin_access_service.pin_service.get_user_pins.return_value = mock_pins
        
        # Act
        result = pin_access_service.get_authorized_pins_for_user(
            requesting_user_id, vault_id, target_user_id
        )
        
        # Assert
        assert len(result) == 1
        assert result[0].user_id == target_user_id
    
    def test_can_user_view_pin_returns_true_for_own_pin(self, pin_access_service):
        """Test that can_user_view_pin returns True for user's own PIN."""
        # Arrange
        user_id = 1
        pin_id = 123
        mock_pin = Mock(spec=KeypadPins, id=pin_id, user_id=user_id, vault_id=456)
        
        pin_access_service.pin_service.get_keypad_pin_by_id.return_value = mock_pin
        
        # Act
        can_view, reason = pin_access_service.can_user_view_pin(user_id, pin_id)
        
        # Assert
        assert can_view is True
        assert "User owns this PIN" in reason
    
    def test_can_user_view_pin_returns_true_for_admin(self, pin_access_service):
        """Test that can_user_view_pin returns True for admin of vault."""
        # Arrange
        user_id = 1
        pin_id = 123
        vault_id = 456
        mock_pin = Mock(spec=KeypadPins, id=pin_id, user_id=2, vault_id=vault_id)
        
        pin_access_service.pin_service.get_keypad_pin_by_id.return_value = mock_pin
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.admin)
        
        # Act
        can_view, reason = pin_access_service.can_user_view_pin(user_id, pin_id)
        
        # Assert
        assert can_view is True
        assert "User is admin of the vault" in reason
    
    def test_can_user_view_pin_returns_false_for_unauthorized_user(self, pin_access_service):
        """Test that can_user_view_pin returns False for unauthorized user."""
        # Arrange
        user_id = 1
        pin_id = 123
        vault_id = 456
        mock_pin = Mock(spec=KeypadPins, id=pin_id, user_id=2, vault_id=vault_id)
        
        pin_access_service.pin_service.get_keypad_pin_by_id.return_value = mock_pin
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.member)
        
        # Act
        can_view, reason = pin_access_service.can_user_view_pin(user_id, pin_id)
        
        # Assert
        assert can_view is False
        assert "User lacks permission to view this PIN" in reason
    
    def test_get_user_pin_permissions_for_member(self, pin_access_service):
        """Test PIN permissions for member user."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.member)
        
        # Act
        permissions = pin_access_service.get_user_pin_permissions(user_id, vault_id)
        
        # Assert
        assert permissions["can_view_own_pins"] is True
        assert permissions["can_view_all_pins"] is False
        assert permissions["can_create_pins"] is True
        assert permissions["can_delete_pins"] is False
        assert permissions["role"] == "member"
    
    def test_get_user_pin_permissions_for_admin(self, pin_access_service):
        """Test PIN permissions for admin user."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.admin)
        
        # Act
        permissions = pin_access_service.get_user_pin_permissions(user_id, vault_id)
        
        # Assert
        assert permissions["can_view_own_pins"] is True
        assert permissions["can_view_all_pins"] is True
        assert permissions["can_create_pins"] is True
        assert permissions["can_delete_pins"] is True
        assert permissions["role"] == "admin"
    
    def test_get_user_pin_permissions_for_guest(self, pin_access_service):
        """Test PIN permissions for guest user."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (True, MembershipRole.guest)
        
        # Act
        permissions = pin_access_service.get_user_pin_permissions(user_id, vault_id)
        
        # Assert
        assert permissions["can_view_own_pins"] is True
        assert permissions["can_view_all_pins"] is False
        assert permissions["can_create_pins"] is False
        assert permissions["can_delete_pins"] is False
        assert permissions["role"] == "guest"
    
    def test_get_user_pin_permissions_for_non_member(self, pin_access_service):
        """Test PIN permissions for non-member user."""
        # Arrange
        user_id = 1
        vault_id = 123
        
        pin_access_service.vault_access_control.check_vault_access_and_role.return_value = (False, None)
        
        # Act
        permissions = pin_access_service.get_user_pin_permissions(user_id, vault_id)
        
        # Assert
        assert permissions["can_view_own_pins"] is False
        assert permissions["can_view_all_pins"] is False
        assert permissions["can_create_pins"] is False
        assert permissions["can_delete_pins"] is False
        assert permissions["role"] is None
        assert "User is not a member of this vault" in permissions["reason"]


class TestPinRepositoryFiltering:
    """Test cases for PIN repository filtering methods."""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return Mock(spec=Session)
    
    def test_get_by_user_and_vault_filters_correctly(self, mock_db):
        """Test that get_by_user_and_vault filters by both user and vault."""
        from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
        
        # Arrange
        repo = KeypadPinsRepository(mock_db)
        user_id = 1
        vault_id = 123
        
        # Act
        repo.get_by_user_and_vault(user_id, vault_id)
        
        # Assert
        mock_db.query.assert_called_once()
        # Verify the filter was applied correctly
        query_call = mock_db.query.return_value.filter
        assert query_call.called
    
    def test_get_by_vault_and_role_filter_for_admin(self, mock_db):
        """Test role-based filtering for admin users."""
        from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
        
        # Arrange
        repo = KeypadPinsRepository(mock_db)
        vault_id = 123
        user_id = 1
        is_admin = True
        
        # Mock the vault pins method
        mock_vault_pins = [Mock(), Mock()]
        repo.get_by_vault_id = Mock(return_value=mock_vault_pins)
        
        # Act
        result = repo.get_by_vault_and_role_filter(vault_id, user_id, is_admin)
        
        # Assert
        assert result == mock_vault_pins
        repo.get_by_vault_id.assert_called_once_with(vault_id)
    
    def test_get_by_vault_and_role_filter_for_member(self, mock_db):
        """Test role-based filtering for member users."""
        from app.repositories.KeyPadPinsRepository import KeypadPinsRepository
        
        # Arrange
        repo = KeypadPinsRepository(mock_db)
        vault_id = 123
        user_id = 1
        is_admin = False
        
        # Mock the user and vault pins method
        mock_user_vault_pins = [Mock()]
        repo.get_by_user_and_vault = Mock(return_value=mock_user_vault_pins)
        
        # Act
        result = repo.get_by_vault_and_role_filter(vault_id, user_id, is_admin)
        
        # Assert
        assert result == mock_user_vault_pins
        repo.get_by_user_and_vault.assert_called_once_with(user_id, vault_id)


if __name__ == "__main__":
    pytest.main([__file__])
