"""
Data models for the app.

Define your app's data models here using SQLAlchemy or Pydantic.
Follow the patterns from the reference apps.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel as PydanticBaseModel, Field

# SQLAlchemy Base for database models
Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields."""
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)


class ExampleEntity(BaseModel):
    """
    Example entity - replace with your actual models.
    
    This is just a template - create your own models based on your app's needs.
    """
    __tablename__ = "example_entities"
    
    name = Column(String(255), nullable=False, index=True)
    description = Column(String(1000))
    
    def __repr__(self):
        return f"<ExampleEntity(id={self.id}, name='{self.name}')>"


# Pydantic models for API requests/responses
class ExampleEntityBase(PydanticBaseModel):
    """Base Pydantic model for ExampleEntity."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class ExampleEntityCreate(ExampleEntityBase):
    """Model for creating new ExampleEntity."""
    pass


class ExampleEntityUpdate(PydanticBaseModel):
    """Model for updating ExampleEntity."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None


class ExampleEntityResponse(ExampleEntityBase):
    """Model for ExampleEntity API responses."""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


# Add your app-specific models here
# 
# Example for a user management app:
# class User(BaseModel):
#     __tablename__ = "users"
#     email = Column(String(255), unique=True, nullable=False, index=True)
#     full_name = Column(String(255), nullable=False)
#     hashed_password = Column(String(255), nullable=False)
#     is_verified = Column(Boolean, default=False)
#
# Example for a document processing app:
# class Document(BaseModel):
#     __tablename__ = "documents"
#     filename = Column(String(255), nullable=False)
#     file_path = Column(String(500), nullable=False)
#     file_size = Column(Integer, nullable=False)
#     mime_type = Column(String(100), nullable=False)
#     processing_status = Column(String(50), default="pending")
#
# Example for an analytics app:
# class Metric(BaseModel):
#     __tablename__ = "metrics"
#     metric_name = Column(String(255), nullable=False, index=True)
#     metric_value = Column(String(255), nullable=False)
#     timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
#     tags = Column(String(500))  # JSON string of tags