from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import timedelta
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user import UserCreate,UserRegister, UserLogin, UpdateUserRole, UserRead
from app.schemas.Response import Response
from app.services.users.UserService import UserService
from app.models.User import User, UserRole
from jose import JWTError, jwt as jose_jwt
from app.core.config import settings
import logging

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/login")

# -----------------------------
# FastAPI router for User endpoints
# -----------------------------
# Handles all HTTP requests related to users:
# - create
# - list
# - fetch by ID
# - login/authentication
# - soft delete
# - role updates (admin functionality)
router = APIRouter(prefix="/users", tags=["users"])

# -----------------------------
# Dependency Functions for FastAPI
# -----------------------------
# These functions provide proper dependency injection for UserService methods

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """
    Dependency function to get current authenticated user.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User object for authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jose_jwt.decode(token, settings.JWT_SECRET, algorithms=settings.ALLOWED_JWT_ALGORITHMS)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        logging.error(f"JWT decode failed: {type(e).__name__}")
        raise credentials_exception

    service = UserService(db)
    user = service.get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency function to check admin access.

    Args:
        current_user: Current authenticated user

    Returns:
        User object if user has admin role

    Raises:
        HTTPException: If user doesn't have admin role
    """
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# -----------------------------
# Create a new user
# -----------------------------
@router.post("/", response_model=Response[UserRead], status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, current_user = Depends(require_admin), db: Session = Depends(get_db)):
    # Need admin role para makapag create.
    """
    Creates a new user.
    - Password is hashed in the UserService.
    - Returns the created user object.
    """
    # Di ko muna i-rerequire by admin role yung pag access dito baka sakaling wala kang user na may admin. 
    # Pero by default dapat for admin access privilege ito.
    service = UserService(db)
    user  = service.create_user(payload.username, payload.email, payload.password)
    return Response(success=True, data=user, detail='User created successfully.')

# -----------------------------
# List all users
# -----------------------------
@router.get("/", response_model=list[UserRead])
def list_users(current_user = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns all users.
    - Could be filtered later to exclude soft-deleted users.
    """
    service = UserService(db)
    return service.list_users()

# -----------------------------
# Get a user by ID
# -----------------------------
@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, current_user = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Fetch a single user by ID.
    - Raises 404 if user not found.
    """
    service = UserService(db)
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

# -----------------------------
# Login endpoint
# -----------------------------
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Verifies user credentials.
    - Returns 401 if login fails.
    - Returns a success message if login succeeds.
    """
    service = UserService(db)
    token = service.authenticate_user(form_data.username, form_data.password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": token, "token_type": "bearer"}

# -----------------------------
# Get current user from token
# -----------------------------


@router.post('/register', response_model=Response[UserRead])
def register(payload: UserRegister, db: Session = Depends(get_db)):
    # New endpoint: /users/register (Tiyaka ko nalang gawan ng independent routes, services, etc)
    """
    Register a new user.
    - Password is hashed in the UserService.
    - Returns HTTP Status of 409 if user already exists.
    - Returns HTTP Status of 422 if password & confirmPassword doesn't match.
    - Returns the created user object.
    """
    service = UserService(db)
    user  = service.register_user(payload.username, payload.email, payload.password, payload.confirmPassword, payload.role)
    return Response(success=True, data=user, detail='User registered successfully.') 
# Get current user from token
# -----------------------------
@router.get("/test/me", response_model=UserRead)
def get_me(current_user: UserRead = Depends(get_current_user)):
    return current_user

# -----------------------------
# Soft delete a user
# -----------------------------
@router.delete("/{user_id}", response_model=Response)
def delete_user(user_id: int, current_user = Depends(require_admin),db: Session = Depends(get_db)):
    """
    Soft deletes a user by ID.
    - Admin role is required.
    - Updates a 'deleted_at' timestamp instead of removing the record.
    - Raises 404 if user not found.
    """
    service = UserService(db)
    user = service.delete_user(user_id)  # implement soft-delete in service/repo
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return Response(success=True, detail=f"User {user_id} deleted successfully")

# -----------------------------
# Update a user's role (admin only)
# -----------------------------
@router.patch("/{user_id}/role", response_model=Response)
def update_user_role(user_id: int, payload: UpdateUserRole, db: Session = Depends(get_db)):
    """
    Update the role of a user.
    - Example: promote to 'admin' or demote to 'user'.
    - Raises 404 if user not found.
    """
    # Di ko muna i-rerequire by admin role yung pag access dito baka sakaling wala kang user na may admin.
    # Pero by default dapat for admin access privilege ito.
    service = UserService(db)
    user = service.update_user_role(user_id, payload.role)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return Response(success=True, detail=f"User {user_id} role successfully updated to {payload.role}")

# -----------------------------
# Get users sharing vault access
# -----------------------------
@router.get("/vault/{user_id}", response_model=list[UserRead])
def get_users_sharing_vault_access(user_id: int, current_user: UserRead = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get all users who share vault access with the specified user.

    This endpoint:
    1. Finds all vaults the specified user has access to
    2. Returns all other users who have access to any of those same vaults
    3. Requires authentication and proper authorization

    Args:
        user_id: The user ID to find shared vault access for
        current_user: The currently authenticated user (injected by dependency)

    Returns:
        List of UserRead objects representing users who share vault access

    Raises:
        403 Forbidden: If current user lacks permission to view this information
        404 Not Found: If the target user doesn't exist
        500 Internal Server Error: If there's a database or server error
    """
    service = UserService(db)
    try:
        shared_users = service.get_users_sharing_vault_access(user_id, current_user)
        return shared_users
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users sharing vault access: {str(e)}"
        )