# SQLModel is built on top of SQLAlchemy + Pydantic.
# - create_engine → opens a connection to the database
# - SQLModel → base class for defining your database models (tables)
from sqlmodel import create_engine, SQLModel

# sessionmaker is a factory that creates new Session objects.
from sqlalchemy.orm import sessionmaker

# python-dotenv loads environment variables from a .env file
from dotenv import load_dotenv
from pathlib import Path

# os lets us read environment variables
import os

# Load variables from .env (ensure correct path when running under reloader subprocess)
# Resolve project root: this file -> app/core/database.py → project root is two levels up
project_root = Path(__file__).resolve().parents[2]
dotenv_path = project_root / ".env"

# Load from explicit path first, then fall back to default search
loaded = False
if dotenv_path.exists():
    loaded = load_dotenv(dotenv_path=str(dotenv_path), override=False)
else:
    loaded = load_dotenv()

print(f"Loaded .env file: path={'project_root/.env' if dotenv_path.exists() else 'default search'} loaded={loaded}")

# Get the database connection string (first pass)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Provide a robust default pointing to a SQLite DB at project root
    default_sqlite_path = (project_root / "smartvault.db").resolve().as_posix()
    DATABASE_URL = f"sqlite:///{default_sqlite_path}"
    # Also set it into environment so subsequent getenv calls see it
    os.environ["DATABASE_URL"] = DATABASE_URL
print(f"DATABASE_URL configured: {DATABASE_URL.split('@')[0] if '@' in DATABASE_URL else DATABASE_URL[:50]}...")

# Pick DB based on environment
ENV = os.getenv("ENV", "dev")  # e.g., dev, test, prod
if ENV == "test":
    DATABASE_URL = os.getenv("TEST_DATABASE_URL")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Final fallback to default SQLite at project root
    default_sqlite_path = (project_root / "smartvault.db").resolve().as_posix()
    DATABASE_URL = f"sqlite:///{default_sqlite_path}"
    os.environ["DATABASE_URL"] = DATABASE_URL
    print("DATABASE_URL was missing; using fallback SQLite at project root")

# Create the database engine
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
engine = create_engine(DATABASE_URL, echo=DEBUG)

# Session factory for DB access
# Every time SessionLocal() is called, you get a new database session (connection to your DB).
# Created at the start of the request (SessionLocal()).
# Used to run queries, inserts, updates, etc. during that request.
# Closed in the finally: block after the request is done — whether it succeeded or failed.
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
    db = SessionLocal() # Creates a new database session (a temporary connection).
    try:
        yield db # Whatever route function depends on get_db, FastAPI will “inject” the db session into it.
    finally:
        # After the route handler is done (whether it succeeded or raised an error), FastAPI ensures this cleanup code runs.
        # It closes the session and releases the connection back to the pool.
        db.close()

# Scoped session for WebSocket (mirrors get_db for manual use)
def get_db_ws():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
