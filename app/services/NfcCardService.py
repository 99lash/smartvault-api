from sqlalchemy.orm import Session
from typing import Optional, List
from app.models.NfcCard import NfcCard
from app.repositories.NfcCardRepository import NfcCardRepository

class NfcCardService:
    """
    Service layer for NFC card operations.

    Encapsulates business logic for managing NFC cards:
    - Creating cards
    - Fetching cards by UID or user
    - Listing all cards
    - Updating or assigning cards to users
    - Soft-deleting cards
    """

    def __init__(self, db: Session):
        """
        Initialize the service with a database session.

        Args:
            db (Session): SQLAlchemy database session.
        """
        self.repo = NfcCardRepository(db)

    def create_card(self, uid: str, name: Optional[str] = None, user_id: Optional[int] = None) -> NfcCard:
        """Create a new NFC card.""" 
        return self.repo.create(uid=uid, name=name, user_id=user_id)

    def get_card_by_uid(self, uid: str) -> Optional[NfcCard]:
        """Retrieve a card by its UID."""
        return self.repo.get_by_uid(uid)

    def get_cards_by_user(self, user_id: int) -> List[NfcCard]:
        """Retrieve all cards assigned to a specific user."""
        return self.repo.get_by_user(user_id)

    def get_all_cards(self) -> List[NfcCard]:
        """
        Retrieve all NFC cards in the system.

        Returns:
            List[NfcCard]: List of all NFC cards, including soft-deleted ones if they exist.
        """
        return self.repo.get_all()

    def assign_card_to_user(self, card_id: int, user_id: int) -> Optional[NfcCard]:
        """Assign an existing NFC card to a user."""
        return self.repo.update(card_id, user_id=user_id)

    def delete_card(self, card_id: int) -> Optional[NfcCard]:
        """Soft-delete an NFC card by ID."""
        return self.repo.delete(card_id)

    def get_all_cards_with_users(self) -> list[tuple[NfcCard, str]]:
        """Get all NFC cards with their assigned usernames."""
        return self.repo.get_all_with_users()
