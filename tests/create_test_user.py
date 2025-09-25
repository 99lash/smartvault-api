#!/usr/bin/env python3
"""
Script to create a test user in the database for testing login functionality.
Run this script to create a user that you can use to test the login.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.User import User, UserRole
from app.core.security import hash_password

# Database configuration
DATABASE_URL = "sqlite:///./smartvault.db"

def create_test_user():
    """Create a test user in the database."""
    # Create database engine
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Create session
    db = SessionLocal()

    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == "testuser").first()
        if existing_user:
            print("Test user already exists!")
            return

        # Create test user
        hashed_password = hash_password("testpass123")
        test_user = User(
            username="testuser",
            email="test@example.com",
            password_hash=hashed_password,
            role=UserRole.user,
            first_name="Test",
            last_name="User"
        )

        db.add(test_user)
        db.commit()
        db.refresh(test_user)

        print("✅ Test user created successfully!")
        print(f"Username: {test_user.username}")
        print(f"Password: testpass123")
        print(f"Email: {test_user.email}")
        print(f"Role: {test_user.role}")
        print(f"User ID: {test_user.id}")

    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_user()