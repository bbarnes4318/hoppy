"""
Transcript model
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy import Index
from app.core.database import Base


class Transcript(Base):
    """Transcript model"""
    __tablename__ = "transcripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id"), unique=True, nullable=False, index=True)
    language = Column(String(10), nullable=False, default="en")
    text = Column(Text, nullable=False)
    words_json = Column(JSONB, nullable=True)  # Word-level timings
    
    # Relationships
    call = relationship("Call", back_populates="transcript")
    
    # Full-text search index
    __table_args__ = (
        Index("idx_transcript_fts", "text", postgresql_using="gin", postgresql_ops={"text": "gin_trgm_ops"}),
    )
    
    def __repr__(self):
        return f"<Transcript(id={self.id}, call_id={self.call_id}, language={self.language})>"

