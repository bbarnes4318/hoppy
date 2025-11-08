"""
Summary model
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, Text, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class Sentiment(str, enum.Enum):
    """Sentiment enum"""
    POSITIVE = "pos"
    NEUTRAL = "neu"
    NEGATIVE = "neg"


class Summary(Base):
    """Summary model"""
    __tablename__ = "summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=False)
    key_points = Column(JSONB, nullable=True)  # Array of strings
    sentiment = Column(SQLEnum(Sentiment), nullable=True)
    
    # Relationships
    call = relationship("Call", back_populates="summary")
    
    def __repr__(self):
        return f"<Summary(id={self.id}, call_id={self.call_id}, sentiment={self.sentiment})>"

