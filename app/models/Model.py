from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

# Reusable base class that inherits from SQLModel
class Model(SQLModel):
    # Auto-incrementing integer primary key
    id: int = Field(primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: Optional[datetime] = Field(default=None, nullable=True)
    # 👇 Soft delete field
    deleted_at: Optional[datetime] = Field(default=None, nullable=True)
