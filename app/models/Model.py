from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import os

# Reusable base class that inherits from SQLModel
class Model(SQLModel):
    # Auto-incrementing integer primary key
    id: int = Field(primary_key=True)

    # Use local timezone for created_at to match user's expectations
    # This ensures dates appear correct in the user's local timezone
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(),  # Local time instead of UTC
        nullable=False
    )
    updated_at: Optional[datetime] = Field(default=None, nullable=True)
    # 👇 Soft delete field
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
