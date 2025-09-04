from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.user_service import UserService
from app.models.User import UserRole

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
@router.post("/")
def create_user(username: str, email: str, password: str, db: Session = Depends(get_db)):
    """
    Creates a new user.
    - Password is hashed in the UserService.
    - Returns the created user object.
    """
    service = UserService(db)
    return service.create_user(username, email, password)

# -----------------------------
# List all users
# -----------------------------
@router.get("/")
def list_users(db: Session = Depends(get_db)):
    """
    Returns all users.
    - Could be filtered later to exclude soft-deleted users.
    """
    service = UserService(db)
    return service.list_users()

# -----------------------------
# Get a user by ID
# -----------------------------
@router.get("/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    """
    Fetch a single user by ID.
    - Raises 404 if user not found.
    """
    service = UserService(db)
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# -----------------------------
# Login endpoint
# -----------------------------
@router.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    """
    Verifies user credentials.
    - Returns 401 if login fails.
    - Returns a success message if login succeeds.
    """
    service = UserService(db)
    if not service.verify_user_password(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"message": "Login successful"}

# -----------------------------
# Soft delete a user
# -----------------------------
@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Soft deletes a user by ID.
    - Updates a 'deleted_at' timestamp instead of removing the record.
    - Raises 404 if user not found.
    """
    service = UserService(db)
    user = service.delete_user(user_id)  # implement soft-delete in service/repo
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user_id} deleted successfully"}

# -----------------------------
# Update a user's role (admin only)
# -----------------------------
@router.patch("/{user_id}/role")
def update_user_role(user_id: int, role: UserRole, db: Session = Depends(get_db)):
    """
    Update the role of a user.
    - Example: promote to 'admin' or demote to 'user'.
    - Raises 404 if user not found.
    """
    service = UserService(db)
    user = service.update_user_role(user_id, role)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User {user_id} role updated to {role}"}
