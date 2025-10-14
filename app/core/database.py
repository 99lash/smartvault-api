from sqlmodel import create_engine, SQLModel
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import os

# Load variables from .env
load_dotenv()
print("Loaded .env file")

# Get the database connection string
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")
else:
    print(f"DATABASE_URL configured: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL[:20]}...")

# Pick DB based on environment
ENV = os.getenv("ENV", "dev")
if ENV == "test":
    DATABASE_URL = os.getenv("TEST_DATABASE_URL")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

# ✅ FIXED: Create the database engine with proper pool configuration
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

engine = create_engine(
    DATABASE_URL,
    echo=DEBUG,
    poolclass=QueuePool,
    pool_size=10,              # ✅ Increased from default 5 to 10
    max_overflow=20,           # ✅ Increased from default 10 to 20
    pool_timeout=30,           # ✅ Wait up to 30 seconds for a connection
    pool_recycle=3600,         # ✅ Recycle connections after 1 hour
    pool_pre_ping=True,        # ✅ Verify connections are alive before using
)

print(f"Database pool configured: size={10}, max_overflow={20}, total_max={30}")

# Session factory for DB access
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize the database (only for dev / first run)
def init_database():
    try:
        print("Initializing database...")
        SQLModel.metadata.create_all(engine)
        print("Database tables created successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise

# Dependency for FastAPI routes
def get_db():
    """
    Database session dependency for FastAPI routes.
    Automatically closes the session after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ✅ REMOVED get_db_ws - use get_db_manual instead
def get_db_manual():
    """
    Manual database session creation for WebSocket handlers.
    MUST be closed manually with db.close() in a try/finally block.
    
    Usage:
        db = get_db_manual()
        try:
            # Use db here
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()  # ✅ ALWAYS close
    """
    return SessionLocal()

# ✅ Optional: Monitor pool health
def get_pool_status():
    """Get current connection pool status for debugging"""
    return {
        "pool_size": engine.pool.size(),
        "checked_out": engine.pool.checkedout(),
        "overflow": engine.pool.overflow(),
        "total_connections": engine.pool.size() + engine.pool.overflow(),
    }