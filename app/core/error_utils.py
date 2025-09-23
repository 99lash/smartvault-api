import logging
from functools import wraps
from fastapi import HTTPException, status
from typing import Callable, Any

from app.core.exceptions import BaseAppException, LogNotFound

logger = logging.getLogger(__name__)

def validate_entity_exists(entity: Any, name: str, entity_id: int) -> Any:
    """
    Validate that an entity exists and raise a LogNotFound exception if it does not.
    
    Args:
        entity: The entity object (e.g., log) retrieved from service.
        name (str): The name of the entity for the error message (e.g., "Log").
        entity_id (int): The ID of the entity.
    
    Returns:
        The entity if it exists.
    
    Raises:
        LogNotFound: If the entity is None or falsy.
    """
    if not entity:
        raise LogNotFound(f"{name} {entity_id} not found")
    return entity

def handle_service_errors() -> Callable:
    """
    Decorator to handle common error patterns in service calls.
    
    Catches BaseAppException and re-raises it for consistent handling.
    Catches other exceptions, logs them, and raises a 500 Internal Server Error
    with consistent format.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except BaseAppException as e:
                # Re-raise custom app exceptions for automatic logging and formatting
                raise e
            except Exception as e:
                # Handle unexpected errors with consistent 500 response
                logger.error(f"Unhandled error in {func.__name__}: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "error": "InternalServerError",
                        "message": "An unexpected error occurred"
                    }
                )
        return wrapper
    return decorator