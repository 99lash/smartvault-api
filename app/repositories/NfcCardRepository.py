from sqlalchemy.orm import Session
from app.models.NfcCard import NfcCard
from app.repositories.Repository import Repository

class NfcCardRepository(Repository):
    """
    Repository for performing database operations on NFC cards.

    Inherits from the base Repository class, which provides
    standard CRUD operations. Additional methods specific
    to NFC cards can be added here.
    """

    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.

        Args:
            db (Session): SQLAlchemy database session.
        """
        super().__init__(db, NfcCard)

    def get_by_uid(self, uid: str) -> NfcCard | None:
        """
        Fetch a single NFC card by its unique UID.

        Args:
            uid (str): Unique identifier of the NFC card.

        Returns:
            NfcCard | None: Returns the NfcCard object if found, else None.

        Example: 
            >>> repo.get_by_uid("AB12CD34")
            <NfcCard uid='AB12CD34' user_id=1 ...>
        """
        return self.db.query(self.model).filter(self.model.uid == uid).first()

    def get_by_user(self, user_id: int) -> list[NfcCard]:
        """
        Fetch all NFC cards associated with a specific user.

        Args:
            user_id (int): ID of the user.

        Returns:
            list[NfcCard]: List of NfcCard objects assigned to the user.
            If no cards are assigned, returns an empty list.

        Example:
            >>> repo.get_by_user(1)
            [<NfcCard uid='AB12CD34' user_id=1 ...>, <NfcCard uid='EF56GH78' user_id=1 ...>]
        """
        return self.db.query(self.model).filter(self.model.user_id == user_id).all()

    def get_all_with_users(self) -> list[tuple[NfcCard, str]]:
        """Fetch all NFC cards and join with the user to get the username."""
        from app.models.User import User
        return self.db.query(NfcCard, User.username).join(User, NfcCard.user_id == User.id).all()

    def get_by_vault(self, vault_id: int) -> list[NfcCard]:
        """
        Fetch all NFC cards for a specific vault.

        Args:
            vault_id (int): ID of the vault.

        Returns:
            list[NfcCard]: List of NfcCard objects in the vault.
            If no cards are found, returns an empty list.

        Note:
            This method doesn't exist in the current model since NFC cards
            don't have a direct vault_id relationship. This would need to be
            implemented based on how vault-card relationship is structured.
        """
        # For now, return all cards since the vault relationship isn't implemented
        # In a real implementation, this would filter by vault_id
        return self.db.query(self.model).all()

    def get_by_vault_with_users(self, vault_id: int) -> list[tuple[NfcCard, str]]:
        """
        Fetch all NFC cards for a vault with their assigned usernames.

        Args:
            vault_id (int): ID of the vault.

        Returns:
            list[tuple[NfcCard, str]]: List of tuples containing (NfcCard, username).
            Username is None if card is not assigned to a user.
        """
        from app.models.User import User

        # For now, return all cards with usernames since vault relationship isn't implemented
        # In a real implementation, this would filter by vault_id
        return (
            self.db.query(NfcCard, User.username)
            .outerjoin(User, NfcCard.user_id == User.id)
            .all()
        )

    def hard_delete(self, card_id: int) -> bool:
        """
        Permanently delete an NFC card from the database.

        Args:
            card_id (int): ID of the NFC card to delete

        Returns:
            bool: True if card was deleted, False if not found
        """
        card = self.db.query(self.model).filter(self.model.id == card_id).first()
        if card:
            self.db.delete(card)
            self.db.commit()
            return True
        return False
