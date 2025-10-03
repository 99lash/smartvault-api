from sqlalchemy.orm import Session
from app.repositories.UserRepository import UserRepository
from app.core.security import hash_password, verify_password
from fastapi.security import HTTPBearer
from fastapi import HTTPException, status, Depends
from app.core.database import get_db
from app.models.User import User, UserRole
from datetime import datetime, timedelta
from jose import JWTError, jwt as jose_jwt
import jwt  # For pyjwt utilities like get_unverified_header
import logging

from app.core.config import settings

# JWT Configuration - All from settings for consistency and configurability
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

bearer_scheme = HTTPBearer()

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
        self.db = db
        self.repo = UserRepository(db)

    def create_user(self, username: str, email: str, password: str, role: UserRole = UserRole.user) -> User:
        """
        Create a new user with hashed password (Admin Privilege).

        Args:
            username: Username for the new user
            email: Email address for the new user
            password: Plain text password (will be hashed)
            role: User role (defaults to UserRole.user)

        Returns:
            Created User object
        """
        hashed_pw = hash_password(password)
        return self.repo.create(username=username, email=email, password_hash=hashed_pw, role=role)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Token expiration time (defaults to ACCESS_TOKEN_EXPIRE_MINUTES)

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jose_jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def register_user(self, username: str, email: str, password: str, confirmPassword: str, role: UserRole = UserRole.user) -> User:
        """
        Register a new user account.

        Args:
            username: Desired username
            email: Email address
            password: Password
            confirmPassword: Password confirmation
            role: User role (defaults to UserRole.user)

        Returns:
            Created User object

        Raises:
            HTTPException: If user already exists or passwords don't match
        """
        user = self.repo.get_by_username(username)
        if user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        if password != confirmPassword:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password does not match")
        hashed_pw = hash_password(password)
        return self.repo.create(username=username, email=email, password_hash=hashed_pw, role=role)

    def get_user_by_id(self, user_id: int) -> User | None:
        """
        Fetch a user by ID.

        Args:
            user_id: User ID to search for

        Returns:
            User object if found, None otherwise
        """
        return self.repo.get_by_id(user_id)

    def get_user_by_username(self, username: str) -> User | None:
        """
        Fetch a user by username.

        Args:
            username: Username to search for

        Returns:
            User object if found, None otherwise
        """
        return self.repo.get_by_username(username)

    def list_users(self) -> list[User]:
        """
        List all users.

        Returns:
            List of all User objects
        """
        return self.repo.get_all()

    def delete_user(self, user_id: int) -> User | None:
        """
        Soft/hard delete a user by ID.

        Args:
            user_id: ID of user to delete

        Returns:
            Deleted User object if found, None otherwise
        """
        return self.repo.delete(user_id)

    def update_user_role(self, user_id: int, role: UserRole) -> User | None:
        """
        Update a user's role.

        Args:
            user_id: ID of user to update
            role: New role for the user

        Returns:
            Updated User object if found, None otherwise
        """
        return self.repo.update_role(user_id, role)

    def authenticate_user(self, username: str, password: str) -> str | None:
        """
        Authenticate user credentials and return JWT token.

        Args:
            username: Username to authenticate
            password: Password to verify

        Returns:
            JWT access token if authentication successful, None otherwise
        """
        user = self.repo.get_by_username(username)
        if not user:
            logging.warning(f"Login attempt failed: User '{username}' not found")
            return None
        if not verify_password(password, user.password_hash):
            logging.warning(f"Login attempt failed: Invalid password for user '{username}'")
            return None
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        return self.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    def get_current_user(self, token = Depends(bearer_scheme)) -> User:
        """
        Get current user from JWT token.

        Args:
            token: JWT token from Authorization header

        Returns:
            User object for the authenticated user

        Raises:
            HTTPException: If token is invalid or user not found
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=settings.ALLOWED_JWT_ALGORITHMS)
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError as e:
            logging.error(f"JWT decode failed: {type(e).__name__}")
            raise credentials_exception

        user = self.repo.get_by_username(username)
        if user is None:
            raise credentials_exception
        return user

    def validate_token(self, token: str) -> User:
        """
        Manual token validation for non-Depends contexts (e.g., WebSocket).
        Raises ValueError on failure.

        Args:
            token: JWT token to validate

        Returns:
            User object for the authenticated user

        Raises:
            ValueError: If token is invalid or user not found
        """
        credentials_exception = ValueError("Could not validate credentials")

        try:
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=settings.ALLOWED_JWT_ALGORITHMS)
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except JWTError as e:
            logging.error(f"JWT decode failed: {type(e).__name__}")
            raise credentials_exception

        user = self.repo.get_by_username(username)
        if user is None:
            logging.warning(f"User not found for username '{username}'")
            raise credentials_exception
        return user
    

    def get_users_sharing_vault_access(self, target_user_id: int, current_user: User) -> list[User]:
        """
        Get all users who share vault access with the specified user.

        This method:
        1. Validates input parameters
        2. Verifies the current user has permission to view this information
        3. Calls UserVaultService to get users sharing vault access
        4. Handles authorization and error cases

        Args:
            target_user_id: The user ID to find shared vault access for (must be positive integer)
            current_user: The currently authenticated user

        Returns:
            List of User objects who share vault access with the target user

        Raises:
            HTTPException: If current user lacks permission or target user doesn't exist
            ValueError: If target_user_id is invalid
        """
        # Input validation
        if not isinstance(target_user_id, int) or target_user_id <= 0:
            raise ValueError("Invalid target_user_id")

        # Authorization check - allow users to view their own data or admins to view any data
        if current_user.id != target_user_id and current_user.role != UserRole.admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view vault access for yourself or as an admin"
            )

        # Verify the target user exists
        target_user = self.get_user_by_id(target_user_id)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target user not found"
            )

        # Import VaultMembershipService here to avoid circular imports
        from app.services.VaultMembershipService import VaultMembershipService

        try:
            vault_service = VaultMembershipService(self.db)
            shared_user_ids = vault_service.get_users_sharing_vault_access(target_user_id)

            # Convert user IDs to User objects
            shared_users = []
            for user_id in shared_user_ids:
                user = self.get_user_by_id(user_id)
                if user:
                    shared_users.append(user)

            return shared_users
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logging.error(f"Error getting users sharing vault access for user {target_user_id}: {type(e).__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error occurred while retrieving vault access information"
            )