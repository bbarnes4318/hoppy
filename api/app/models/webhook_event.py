"""
Webhook event model (for ingestion auditing)
"""
import uuid
from sqlalchemy import Column, String, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base
import enum
from datetime import datetime


class WebhookStatus(str, enum.Enum):
    """Webhook status enum"""
    RECEIVED = "received"
    PROCESSED = "processed"
    ERROR = "error"


class WebhookEvent(Base):
    """Webhook event model"""
    __tablename__ = "webhook_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(SQLEnum(WebhookStatus), nullable=False, default=WebhookStatus.RECEIVED)
    error_message = Column(String(1000), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<WebhookEvent(id={self.id}, source={self.source}, status={self.status})>"

