from sqlalchemy.orm import Session
from app.repositories.UserRepository import UserRepository
from app.core.security import hash_password, verify_password
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, status, Depends
from app.core.database import get_db
from app.models.User import User, UserRole
from datetime import datetime, timedelta
from jose import JWTError, jwt

SECRET_KEY = "a699f178b8b83de7721314c70f2fdcd78f58a1a793a7c7ed1ce32c5e2dea348f"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

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

    # Create a new user with hashed password (Admin Privilege)
    def create_user(self, username: str, email: str, password: str, role: UserRole = UserRole.user) -> User:
        hashed_pw = hash_password(password)
        return self.repo.create(username=username, email=email, password_hash=hashed_pw, role=role)

    def create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    def register_user(self, username: str, email: str, password: str, confirmPassword: str, role: UserRole = UserRole.user) -> User:
        user = self.repo.get_by_username(username)
        if user:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
        if (password != confirmPassword):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password does not match")
        hashed_pw = hash_password(password)
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

      # Authenticate and issue JWT
    def authenticate_user(self, username: str, password: str) -> str | None:
        user = self.repo.get_by_username(username)
        if not user or not verify_password(password, user.password_hash):
            return None
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        return self.create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    # Get current user from token
    @staticmethod
    def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
        print("meow")
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub") # type: ignore
            if username is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        repo = UserRepository(db)
        user = repo.get_by_username(username)
        if user is None:
            raise credentials_exception
        return user
    
    @staticmethod
    def require_admin(current_user = Depends(get_current_user)):
        if current_user.role != UserRole.admin: # type: ignore
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return current_user