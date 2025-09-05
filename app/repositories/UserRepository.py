from sqlalchemy.orm import Session
from app.models.User import User, UserRole
from app.repositories.Repository import Repository  # assuming you saved BaseRepository in base.py

class UserRepository(Repository):
    def __init__(self, db: Session):
        super().__init__(db, User)

    # Get a user by username (only active)
    def get_by_username(self, username: str):
        return (
            self.db.query(self.model)
            .filter(self.model.username == username, self.model.deleted_at == None)
            .first()
        )

    # Update user role
    def update_role(self, user_id: int, role: UserRole):
        return self.update(user_id, role=role)

    # Optional: restore a soft-deleted user
    def restore(self, user_id: int):
        user = self.db.query(self.model).filter(self.model.id == user_id, self.model.deleted_at != None).first()
        if user:
            user.deleted_at = None
            self.db.commit()
            self.db.refresh(user)
        return user

    # Optional: get all deleted users
    def get_deleted(self):
        return self.db.query(self.model).filter(self.model.deleted_at != None).all()
