from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.users.UserService import UserService
from app.models.User import User


def get_current_user(
    authorization: str = Header(..., description="Bearer access token"),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to extract and validate the current user from the Authorization header.
    Raises 401 if no valid Bearer token is provided.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.split(" ")[1]
    user_service = UserService(db)
    return user_service.validate_token(token)


def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to ensure the current user has system-wide admin role.
    Raises 403 if the user is not an admin.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
