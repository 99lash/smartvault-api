from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

# Reusable base class that inherets from SQLModel
class Model(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)                       
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)   
    updated_at: Optional[datetime] = None
    # 👇 Soft delete field
    deleted_at: Optional[datetime] = None
