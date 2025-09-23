from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List
from app.core.enums import LogPrefixesEnum

load_dotenv()

class Settings(BaseSettings):
    # Existing settings
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "your-secret-key"
    API_V1_STR: str = "/api/v1"

    # Log configuration
    DEFAULT_LOG_PREFIXES: List[LogPrefixesEnum] = [
        LogPrefixesEnum.DUAL,
        LogPrefixesEnum.TAMPER,
        LogPrefixesEnum.FAILURE,
        LogPrefixesEnum.MANUAL
    ]
    DEFAULT_PAGINATION_LIMIT: int = 100
    DEV_LOG_PREFIXES: List[LogPrefixesEnum] = DEFAULT_LOG_PREFIXES + [LogPrefixesEnum.ALARM]  # More verbose in dev
    PROD_LOG_PREFIXES: List[LogPrefixesEnum] = [LogPrefixesEnum.TAMPER, LogPrefixesEnum.FAILURE]  # Security-focused in prod

    @property
    def DEFAULT_LOG_PREFIXES_STR(self) -> List[str]:
        return [p.value for p in self.DEFAULT_LOG_PREFIXES]

    # WebSocket configuration
    WS_MAX_CONNECTIONS: int = 100
    WS_TIMEOUT_SECONDS: int = 30
    DEV_WS_MAX_CONNECTIONS: int = 50  # Lower in dev for testing
    PROD_WS_MAX_CONNECTIONS: int = 200  # Higher in prod

    # Logging
    LOG_LEVEL: str = "INFO"
    DEV_LOG_LEVEL: str = "DEBUG"
    PROD_LOG_LEVEL: str = "WARNING"

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = "../.env"  # Relative to app/

settings = Settings()

# Environment-specific settings
if settings.ENVIRONMENT == "production":
    settings.LOG_LEVEL = settings.PROD_LOG_LEVEL
    settings.DEFAULT_LOG_PREFIXES = settings.PROD_LOG_PREFIXES
    settings.WS_MAX_CONNECTIONS = settings.PROD_WS_MAX_CONNECTIONS
else:
    settings.LOG_LEVEL = settings.DEV_LOG_LEVEL
    settings.DEFAULT_LOG_PREFIXES = settings.DEV_LOG_PREFIXES
    settings.WS_MAX_CONNECTIONS = settings.DEV_WS_MAX_CONNECTIONS