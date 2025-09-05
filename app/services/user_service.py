from sqlalchemy.orm import Session
from app.repositories.UserRepository import UserRepository
from app.core.security import hash_password, verify_password
from app.models.User import User, UserRole

# -----------------------------
# Service layer for User logic
# -----------------------------
# Encapsulates business logic related to users:
# - password hashing
# - using DB operations to UserRepository
# - verification of credentials
class UserService:
    def __init__(self, db: Session):
        # Initialize repository with a database session
        self.repo = UserRepository(db)

    # Create a new user with hashed password
    def create_user(self, username: str, email: str, password: str, role: UserRole = UserRole.user) -> User:
        hashed_pw = hash_password(password)  # securely hash password before storing
        return self.repo.create(username=username, email=email, password_hash=hashed_pw, role=role)

    # Fetch a user by ID
    def get_user_by_id(self, user_id: int) -> User | None:
        return self.repo.get_by_id(user_id)

    # Fetch a user by username
    def get_user_by_username(self, username: str) -> User | None:
        return self.repo.get_by_username(username)

    # List all users
    def list_users(self) -> list[User]:
        return self.repo.get_all()

    # Soft/hard delete a user by ID
    def delete_user(self, user_id: int) -> User | None:
        return self.repo.delete(user_id)

    # Update a user's role (e.g., admin or user)
    def update_user_role(self, user_id: int, role: UserRole) -> User | None:
        return self.repo.update_role(user_id, role)

    # Verify a user's password (used for login)
    def verify_user_password(self, username: str, password: str) -> bool:
        """Check if a user's password is valid (used for login)."""
        user = self.repo.get_by_username(username)
        if not user:
            return False  # username not found
        return verify_password(password, user.password_hash)  # compare with hashed password
