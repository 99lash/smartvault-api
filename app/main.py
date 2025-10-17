from fastapi import FastAPI;
from app.core.security import verify_password
from app.core.database import init_database
from app.routes.user_routes import router as user_router
from app.routes.keypadpin_routes import router as keypadpin_router
from app.routes.log_routes import router as log_router
from app.routes.nfccard_routes import router as nfccard_routes
from app.routes.vault_invitation_routes import router as vault_invitation_router
from app.routes.vault_membership_routes import router as vault_membership_router
from app.routes.vault_routes import router as vault_routes_router

# Redis imports
import redis
from redis.asyncio import Redis as AsyncRedis
from app.core.config import settings
from app.services.logs.BruteforceDetectionService import BruteforceDetectionService
from app.services.events.EventManager import EventManager

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title='smartvault_api')

# Global Redis services (initialized during startup)
redis_client = None
async_redis_client = None
bruteforce_service = None
event_manager = None

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables if they don't exist
try:
    init_database()
    print("Application startup: Database initialized successfully")
except Exception as e:
    print(f"Application startup failed: Database init error - {e}")
    raise

# Initialize Redis clients
try:
    # Synchronous Redis client for blocking operations
    redis_client = redis.Redis.from_url(settings.REDIS_URL)
    redis_client.ping()  # Test connection
    print("Application startup: Redis connected successfully")

    # Asynchronous Redis client for async operations
    async_redis_client = AsyncRedis.from_url(settings.REDIS_URL)
    print("Application startup: Async Redis client created")

    # Initialize Redis-dependent services
    from app.core.database import get_db
    db_session = next(get_db())  # Get a database session for services

    # Initialize bruteforce detection service
    bruteforce_service = BruteforceDetectionService(redis_client, db_session)
    print("Application startup: BruteforceDetectionService initialized")

    # Initialize event manager for WebSocket broadcasting
    event_manager = EventManager(async_redis_client)
    print("Application startup: EventManager initialized")

    # Make services available globally
    app.state.redis_client = redis_client
    app.state.async_redis_client = async_redis_client
    app.state.bruteforce_service = bruteforce_service
    app.state.event_manager = event_manager

except Exception as e:
    print(f"Application startup failed: Redis init error - {e}")
    print("Warning: Redis-dependent features will not be available")
    # Make services available globally as None
    app.state.redis_client = None
    app.state.async_redis_client = None
    app.state.bruteforce_service = None
    app.state.event_manager = None

# Include routes
app.include_router(user_router)
app.include_router(vault_routes_router)
app.include_router(keypadpin_router)
app.include_router(log_router)
app.include_router(nfccard_routes)
app.include_router(vault_invitation_router)
app.include_router(vault_membership_router)



