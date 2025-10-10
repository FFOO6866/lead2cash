"""
Business logic services for the app.

Put your business logic here, separate from API endpoints and data models.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from .models import ExampleEntity, ExampleEntityCreate, ExampleEntityUpdate


class BaseService:
    """Base service class with common functionality."""
    
    def __init__(self, db: Session):
        self.db = db


class ExampleService(BaseService):
    """
    Service for ExampleEntity operations.
    
    This is a template - replace with your actual business logic.
    """
    
    def create_entity(self, entity_data: ExampleEntityCreate) -> ExampleEntity:
        """Create a new entity."""
        entity = ExampleEntity(**entity_data.dict())
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    def get_entity(self, entity_id: int) -> Optional[ExampleEntity]:
        """Get entity by ID."""
        return self.db.query(ExampleEntity).filter(
            ExampleEntity.id == entity_id,
            ExampleEntity.is_active == True
        ).first()
    
    def get_entities(self, skip: int = 0, limit: int = 100) -> List[ExampleEntity]:
        """Get list of entities."""
        return self.db.query(ExampleEntity).filter(
            ExampleEntity.is_active == True
        ).offset(skip).limit(limit).all()
    
    def update_entity(self, entity_id: int, entity_data: ExampleEntityUpdate) -> Optional[ExampleEntity]:
        """Update an entity."""
        entity = self.get_entity(entity_id)
        if not entity:
            return None
        
        update_data = entity_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(entity, field, value)
        
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    def delete_entity(self, entity_id: int) -> bool:
        """Soft delete an entity."""
        entity = self.get_entity(entity_id)
        if not entity:
            return False
        
        entity.is_active = False
        self.db.commit()
        return True
    
    def search_entities(self, query: str) -> List[ExampleEntity]:
        """Search entities by name."""
        return self.db.query(ExampleEntity).filter(
            ExampleEntity.name.ilike(f"%{query}%"),
            ExampleEntity.is_active == True
        ).all()


# Add your app-specific services here
#
# Example for user management app:
# class UserService(BaseService):
#     def authenticate_user(self, email: str, password: str) -> Optional[User]:
#         # Authentication logic
#         pass
#     
#     def create_user(self, user_data: UserCreate) -> User:
#         # User creation with password hashing
#         pass
#     
#     def verify_user_email(self, user_id: int, verification_token: str) -> bool:
#         # Email verification logic
#         pass
#
# Example for document processing app:
# class DocumentService(BaseService):
#     def upload_document(self, file_data: bytes, filename: str) -> Document:
#         # File upload and storage logic
#         pass
#     
#     def process_document(self, document_id: int) -> bool:
#         # Document processing using Kailash workflows
#         pass
#     
#     def get_processing_status(self, document_id: int) -> str:
#         # Check document processing status
#         pass
#
# Example for analytics app:
# class MetricsService(BaseService):
#     def record_metric(self, metric_name: str, value: str, tags: dict = None) -> Metric:
#         # Record a new metric
#         pass
#     
#     def get_metrics(self, metric_name: str, start_date: datetime, end_date: datetime) -> List[Metric]:
#         # Get metrics in date range
#         pass
#     
#     def aggregate_metrics(self, metric_name: str, aggregation: str = "sum") -> dict:
#         # Aggregate metrics data
#         pass