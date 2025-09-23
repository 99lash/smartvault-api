import logging
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

class BaseAppException(HTTPException):
    """
    Base exception class for application errors.
    
    Provides consistent error format: {"error": class_name, "message": detail}
    Automatically logs errors for debugging.
    """
    def __init__(self, status_code: int, detail: str):
        error_detail = {
            "error": self.__class__.__name__,
            "message": detail
        }
        super().__init__(status_code=status_code, detail=error_detail)
        logger.error(f"{self.__class__.__name__}: {detail}")

class LogNotFound(BaseAppException):
    """
    Exception raised when a log entry is not found.
    """
    def __init__(self, detail: str = "Log not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

class NoMatchingLogsFound(BaseAppException):
    """
    Exception raised when no matching logs are found for the query.
    """
    def __init__(self, detail: str = "No matching logs found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)