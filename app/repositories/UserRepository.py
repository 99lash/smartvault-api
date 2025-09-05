from sqlalchemy.orm import Session
from datetime import datetime
from app.models.User import User, UserRole


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    # Get all active (non-deleted) users
    def get_all(self):
        return self.db.query(User).filter(User.deleted_at == None).all()

    # Get a user by ID (only active)
    def get_by_id(self, user_id: int):
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at == None)
            .first()
        )

    # Get a user by username (only active)
    def get_by_username(self, username: str):
        return (
            self.db.query(User)
            .filter(User.username == username, User.deleted_at == None)
            .first()
        )

    # Create a new user
    def create(self, username: str, email: str, password_hash: str, role: UserRole = UserRole.user):
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)  # refresh to get new id, created_at, etc.
        return new_user

    # Update user role (or any other field later)
    def update_role(self, user_id: int, role: UserRole):
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.role = role
        self.db.commit()
        self.db.refresh(user)
        return user

    # Soft delete a user
    def delete(self, user_id: int):
        user = self.get_by_id(user_id)
        if user:
            user.deleted_at = datetime.utcnow()  # mark as deleted
            self.db.commit()
            self.db.refresh(user)
        return user

    # Restore a soft-deleted user (optional helper)
    def restore(self, user_id: int):
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.deleted_at != None)
            .first()
        )
        if user:
            user.deleted_at = None
            self.db.commit()
            self.db.refresh(user)
        return user

    # Get all deleted users (optional helper)
    def get_deleted(self):
        return self.db.query(User).filter(User.deleted_at != None).all()
