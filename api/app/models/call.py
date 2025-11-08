"""
Call model
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, Boolean, Integer, DateTime, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
from datetime import datetime


class CallDisposition(str, enum.Enum):
    """Call disposition enum"""
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    REJECTED = "rejected"


class Call(Base):
    """Call model"""
    __tablename__ = "calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=True, index=True)
    external_call_id = Column(String(255), nullable=True, index=True)
    
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_sec = Column(Integer, nullable=True)
    
    disposition = Column(SQLEnum(CallDisposition), nullable=False)
    billable = Column(Boolean, nullable=False, default=False, index=True)
    sale_made = Column(Boolean, nullable=False, default=False, index=True)
    sale_amount_cents = Column(Integer, nullable=True)
    
    ani = Column(String(50), nullable=True)  # Caller number
    dnis = Column(String(50), nullable=True)  # Destination number
    agent_name = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="calls")
    partner = relationship("Partner", back_populates="calls")
    transcript = relationship("Transcript", back_populates="call", uselist=False, cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="call", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Call(id={self.id}, external_call_id={self.external_call_id}, disposition={self.disposition})>"

