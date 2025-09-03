from sqlmodel import create_engine, SQLModel
from dotenv import load_dotenv
import os

load_dotenv()  # load .env file

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)
