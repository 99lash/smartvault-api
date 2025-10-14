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
