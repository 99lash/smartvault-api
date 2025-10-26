import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, Field, model_validator
from app.core.database import get_db
from app.services.NfcCardService import NfcCardService
from app.services.users.UserService import UserService
from app.models.User import User
from app.schemas.nfc_card import NfcCardCreate, NfcCardAssign, NfcCardRead, NfcCardWithUser
from app.schemas.Response import Response
from app.core.dependencies import get_current_admin, get_current_user
from app.services.vaults.VaultMembershipService import VaultMembershipService
from app.services.VaultAccessControlService import VaultAccessControlService
from app.services.NfcCardAccessControlService import NfcCardAccessControlService
from app.models.VaultMembership import MembershipRole

# Configure logging
logger = logging.getLogger(__name__)

# Pydantic models for input validation
class NFCCardListQueryParams(BaseModel):
    """Query parameters for listing NFC cards with validation."""
    user_id: Optional[int] = Field(None, gt=0, description="Filter cards by user ID")
    vault_id: Optional[int] = Field(None, gt=0, description="Filter cards by vault ID")

    @model_validator(mode='after')
    def validate_mutual_exclusivity(self):
        """Ensure only one filter parameter is provided."""
        if self.user_id is not None and self.vault_id is not None:
            raise ValueError("Provide either user_id or vault_id, but not both")
        return self


# -----------------------------
# Helper Functions
# -----------------------------

def _validate_nfc_card_listing_parameters(user_id: int | None, vault_id: int | None) -> None:
    """
    Validate parameters for NFC card listing endpoint.

    Args:
        user_id: User ID parameter
        vault_id: Vault ID parameter

    Raises:
        HTTPException: If parameters are invalid
    """
    # Validate user_id parameter
    if user_id is not None and user_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must be greater than 0"
        )

    # Validate vault_id parameter
    if vault_id is not None and vault_id < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="vault_id must be greater than 0"
        )

    # Validate mutual exclusivity
    if user_id is not None and vault_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either user_id or vault_id, but not both"
        )

router = APIRouter(
    prefix="/nfc-cards",
    tags=["NFC Cards"],
    redirect_slashes=False  
)


# -----------------------------
# Get all NFC cards with usernames
# -----------------------------
@router.get("/users", response_model=List[NfcCardWithUser])
def list_nfc_cards_with_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns NFC cards with usernames based on user role and vault permissions.
    - Members see only their own cards across all vaults
    - Admins see all cards in vaults they manage
    - Guests see no cards
    """
    # Initialize access control service
    nfc_access_control = NfcCardAccessControlService(db)

    # Get all cards the user is authorized to view
    authorized_cards = nfc_access_control.get_authorized_cards_for_user(
        user_id=current_user.id
    )

    # Enhance cards with user information using service layer
    service = NfcCardService(db)
    enhanced_cards = service.enhance_cards_with_user_info(authorized_cards, db)

    # Convert to NfcCardWithUser schema format
    return [
        NfcCardWithUser(
            nfc_card_id=card['id'],
            nfc_card_uid=card['uid'],
            nfc_card_name=card['name'],
            vault_id=card['vault_id'],
            user_id=card['user_id'],
            username=card['username'] or "Unassigned"
        )
        for card in enhanced_cards
    ]

def _validate_and_get_card_assignment(current_user: User, payload: NfcCardCreate, access_control: VaultAccessControlService) -> tuple[int, MembershipRole]:
    """
    Validate user permissions and determine card assignment based on role.

    Args:
        current_user: Currently authenticated user
        payload: NFC card creation data
        access_control: Vault access control service

    Returns:
        Tuple of (user_id, role)

    Raises:
        HTTPException: If validation fails
    """
    # Check vault membership and get user role
    is_member, role = access_control.check_vault_access_and_role(current_user.id, payload.vault_id)

    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this vault"
        )

    # Enforce role-based limits
    access_control.enforce_nfc_card_limit(current_user.id, payload.vault_id)

    # Determine user_id based on role
    if role == MembershipRole.member:
        # Members must have the card assigned to themselves
        user_id = current_user.id
    elif role == MembershipRole.admin:
        # Admins can choose to assign or leave unassigned
        user_id = payload.user_id
    else:
        # Guests cannot create cards (should be caught by enforce_nfc_card_limit)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest users cannot create NFC cards"
        )

    return user_id, role


def _create_card_response(nfc_card: NfcCardRead, role: MembershipRole, user_id: Optional[int]) -> Response[NfcCardRead]:
    """
    Create response message based on role and assignment.

    Args:
        nfc_card: Created NFC card
        role: User's role in the vault
        user_id: ID of assigned user (if any)

    Returns:
        Response object with appropriate message
    """
    if role == MembershipRole.member:
        detail = "NFC Card successfully created and assigned to you"
    else:
        assignment_msg = f" and assigned to user {user_id}" if user_id else " (unassigned)"
        detail = f"NFC Card successfully created{assignment_msg}"

    return Response(success=True, data=nfc_card, detail=detail)


# -----------------------------
# Create a new NFC card
# -----------------------------
@router.post("/", response_model=Response[NfcCardRead], status_code=status.HTTP_201_CREATED)
def create_nfc_card(payload: NfcCardCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Creates a new NFC card record with role-based access control.

    Role-based behavior:
    - MEMBER: Limited to 1 NFC card per vault, automatically assigned to themselves
    - ADMIN: Unlimited NFC cards, can assign to any vault member or leave unassigned
    - GUEST: Cannot create NFC cards (read-only access)

    Args:
        payload: NFC card creation data including uid, vault_id, name, and optional user_id
        current_user: Currently authenticated user
        db: Database session
    """
    try:
        logger.info(f"NFC card creation attempt by user {current_user.id} for vault {payload.vault_id}")

        # Initialize access control service
        access_control = VaultAccessControlService(db)

        # Validate permissions and determine assignment
        user_id, role = _validate_and_get_card_assignment(current_user, payload, access_control)

        # Create the NFC card
        service = NfcCardService(db)
        nfc_card = service.create_card(
            uid=payload.uid,
            vault_id=payload.vault_id,
            name=payload.name,
            user_id=user_id
        )

        logger.info(f"NFC card {nfc_card.id} successfully created by user {current_user.id}")

        # Prepare and return response
        return _create_card_response(nfc_card, role, user_id)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating NFC card for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}"
        )

# -----------------------------
# Get all NFC cards with optional filtering
# -----------------------------
@router.get("/", response_model=List[NfcCardRead])
def list_nfc_cards(
    query_params: NFCCardListQueryParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns NFC cards with optional filtering and proper authorization.

    Query Parameters:
    - user_id: Filter cards by specific user ID (mutually exclusive with vault_id)
    - vault_id: Filter cards by vault ID (mutually exclusive with user_id)

    Authorization:
    - Users can only view their own cards unless they're admin of the vault
    - Admins can view all cards in vaults they manage
    - Guests cannot view any cards

    Note: Provide either user_id OR vault_id, but not both.
    If no filters are provided, returns user's own cards.
    """
    try:
        # Input validation
        _validate_nfc_card_listing_parameters(query_params.user_id, query_params.vault_id)

        # Initialize access control service
        nfc_access_control = NfcCardAccessControlService(db)

        # Get authorized cards based on user role and filters
        authorized_cards = nfc_access_control.get_authorized_cards_for_user(
            user_id=current_user.id,
            vault_id=query_params.vault_id,
            target_user_id=query_params.user_id
        )

        logger.debug(f"Returning {len(authorized_cards)} authorized NFC cards for user {current_user.id}")
        return authorized_cards

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing NFC cards for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching NFC cards: {str(e)}"
        )

# -----------------------------
# Get NFC card by UID
# -----------------------------
@router.get("/uid/{uid}", response_model=NfcCardRead)
def get_card_by_uid(uid: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch a single NFC card by UID with authorization checks.
    - Users can only view cards they own or cards in vaults they admin
    - Raises 404 if not found or access denied.
    """
    service = NfcCardService(db)
    card = service.get_card_by_uid(uid)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    # Check authorization using access control service
    nfc_access_control = NfcCardAccessControlService(db)
    can_view, reason = nfc_access_control.can_user_view_card(current_user.id, card.id)
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    return card

# -----------------------------
# Get all cards assigned to a user
# -----------------------------
@router.get("/user/{user_id}", response_model=List[NfcCardRead])
def get_cards_by_user(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch user's NFC cards with authorization checks.
    - Users can only view their own cards unless they're admin
    - Raises 404 if user not found.
    """
    # Initialize access control service
    nfc_access_control = NfcCardAccessControlService(db)
    
    # Get authorized cards for the target user
    authorized_cards = nfc_access_control.get_authorized_cards_for_user(
        user_id=current_user.id,
        target_user_id=user_id
    )
    
    return authorized_cards

# -----------------------------
# Assign card to user
# -----------------------------
@router.patch("/{card_id}/assign", response_model=Response)
def assign_card_to_user(card_id: int, payload: NfcCardAssign, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Assigns an existing NFC card to a user with vault admin authorization.
    - Only vault admins can assign cards in their vaults
    - Updates the `user_id` field.
    - Raises 404 if NFC card or user not found.
    """
    # Get the NFC card to find its vault
    nfc_service = NfcCardService(db)
    card = nfc_service.get_card_by_id(card_id)
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    # Check if user is admin of the vault containing this NFC card using access control service
    nfc_access_control = NfcCardAccessControlService(db)
    can_assign, reason = nfc_access_control.can_user_assign_card(current_user.id, card_id)
    if not can_assign:
        logger.warning(f"User {current_user.id} attempted to assign NFC card {card_id}: {reason}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    # Validate target user exists
    user_service = UserService(db)
    user = user_service.get_user_by_id(payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Assign the card
    updated_card = nfc_service.assign_card_to_user(card_id, payload.user_id)
    if not updated_card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Failed to assign NFC card")

    return Response(success=True, detail=f"NFC Card {card_id} assigned to user {payload.user_id}")

# -----------------------------
# Get all NFC cards for a specific vault with usernames
# -----------------------------
@router.get("/vault/{vault_id}", response_model=List[NfcCardWithUser])
def get_cards_by_vault(vault_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Returns all NFC cards for a specific vault with usernames.

    Authorization:
    - User must be a member of the vault
    - Members can only see their own cards in this vault
    - Admins can see all cards in the vault
    - Guests cannot see any cards

    Raises:
    - 403: If user is not a member of the vault or lacks permissions
    - 500: If an unexpected error occurs
    """
    # Initialize access control service
    nfc_access_control = NfcCardAccessControlService(db)
    
    # Get authorized cards based on user role
    authorized_cards = nfc_access_control.get_authorized_cards_for_user(
        user_id=current_user.id,
        vault_id=vault_id
    )
    
    # Enhance cards with user information using service layer
    service = NfcCardService(db)
    enhanced_cards = service.enhance_cards_with_user_info(authorized_cards, db)

    # Convert to NfcCardWithUser schema format
    return [
        NfcCardWithUser(
            nfc_card_id=card['id'],
            nfc_card_uid=card['uid'],
            nfc_card_name=card['name'],
            vault_id=card['vault_id'],
            user_id=card['user_id'],
            username=card['username'] or "Unassigned"
        )
        for card in enhanced_cards
    ]
# -----------------------------
# Hard delete a NFC card (permanent deletion)
# -----------------------------
@router.delete("/{card_id}/hard", response_model=Response)
def hard_delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Permanently deletes an NFC card by ID.
    - WARNING: This action cannot be undone!
    - Raises 404 if not found.
    - Requires vault admin access for the vault containing the NFC card.
    """
    logger.info(f"NFC card hard delete attempt by user {current_user.id} ({current_user.username}) for card {card_id}")

    # Get the NFC card to find its vault
    service = NfcCardService(db)
    nfc_card = service.get_card_by_id(card_id)
    if not nfc_card:
        logger.warning(f"NFC card {card_id} not found for hard delete by user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    logger.debug(f"NFC card found: ID={nfc_card.id}, UID={nfc_card.uid}, Vault ID={nfc_card.vault_id}")

    # Check if user is admin of the vault containing this NFC card using access control service
    nfc_access_control = NfcCardAccessControlService(db)
    can_delete, reason = nfc_access_control.can_user_delete_card(current_user.id, card_id)
    if not can_delete:
        logger.warning(f"User {current_user.id} attempted to hard delete NFC card {card_id}: {reason}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    # Proceed with deletion
    deleted = service.hard_delete_card(card_id)
    if not deleted:
        logger.error(f"Failed to hard delete NFC card {card_id} by user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    logger.info(f"NFC card {card_id} permanently deleted by user {current_user.id}")
    return Response(success=True, detail=f"NFC card {card_id} permanently deleted")

# -----------------------------
# Soft delete a NFC card
# -----------------------------
@router.delete("/{card_id}", response_model=Response)
def delete_nfc_card(card_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Deletes an NFC card by ID.
    - Soft deletes if the model has a deleted_at column.
    - Raises 404 if not found.
    - Requires vault admin access for the vault containing the NFC card.
    """
    logger.info(f"NFC card soft delete attempt by user {current_user.id} ({current_user.username}) for card {card_id}")

    # Get the NFC card to find its vault
    service = NfcCardService(db)
    nfc_card = service.get_card_by_id(card_id)
    if not nfc_card:
        logger.warning(f"NFC card {card_id} not found for soft delete by user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    logger.debug(f"NFC card found: ID={nfc_card.id}, UID={nfc_card.uid}, Vault ID={nfc_card.vault_id}")

    # Check if user is admin of the vault containing this NFC card using access control service
    nfc_access_control = NfcCardAccessControlService(db)
    can_delete, reason = nfc_access_control.can_user_delete_card(current_user.id, card_id)
    if not can_delete:
        logger.warning(f"User {current_user.id} attempted to soft delete NFC card {card_id}: {reason}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    # Proceed with deletion
    card = service.delete_card(card_id)
    if not card:
        logger.error(f"Failed to soft delete NFC card {card_id} by user {current_user.id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NFC card not found")

    logger.info(f"NFC card {card_id} soft deleted by user {current_user.id}")
    return Response(success=True, detail=f"NFC card {card_id} deleted successfully")
