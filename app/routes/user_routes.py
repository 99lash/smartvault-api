from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.user import UserCreate, UserLogin, UpdateUserRole, UserRead
from app.schemas.Response import Response
from app.services.UserService import UserService

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
# Create a new user
# -----------------------------
@router.post("/", response_model=Response[UserRead], status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
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
def list_users(current_user = Depends(UserService.require_admin), db: Session = Depends(get_db)):
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
def get_user(user_id: int, current_user = Depends(UserService.require_admin), db: Session = Depends(get_db)):
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
@router.get("/test/me", response_model=UserRead)
def get_me(current_user: UserRead = Depends(UserService.get_current_user)):
    return current_user

# -----------------------------
# Soft delete a user
# -----------------------------
@router.delete("/{user_id}", response_model=Response)
def delete_user(user_id: int, current_user = Depends(UserService.require_admin),db: Session = Depends(get_db)):
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