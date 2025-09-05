# SQLModel is built on top of SQLAlchemy + Pydantic.
# - create_engine → opens a connection to the database
# - SQLModel → base class for defining your database models (tables)
from sqlmodel import create_engine, SQLModel

# sessionmaker is a factory that creates new Session objects.
from sqlalchemy.orm import sessionmaker

# python-dotenv loads environment variables from a .env file
from dotenv import load_dotenv

# os lets us read environment variables
import os

# Load variables from .env
load_dotenv()

# Get the database connection string
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")

# Pick DB based on environment
ENV = os.getenv("ENV", "dev")  # e.g., dev, test, prod
if ENV == "test":
    DATABASE_URL = os.getenv("TEST_DATABASE_URL")
else:
    DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

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
    SQLModel.metadata.create_all(engine)

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal() # Creates a new database session (a temporary connection).
    try:
        yield db # Whatever route function depends on get_db, FastAPI will “inject” the db session into it.
    finally:
        # After the route handler is done (whether it succeeded or raised an error), FastAPI ensures this cleanup code runs.
        # It closes the session and releases the connection back to the pool.
        db.close()
