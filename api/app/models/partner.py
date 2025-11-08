"""
Partner model (publishers, agencies, brokers)
"""
import uuid
from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class PartnerKind(str, enum.Enum):
    """Partner kind enum"""
    PUBLISHER = "publisher"
    AGENCY = "agency"
    BROKER = "broker"


class Partner(Base):
    """Partner model (normalized publishers/agencies/brokers)"""
    __tablename__ = "partners"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    kind = Column(SQLEnum(PartnerKind), nullable=False)
    name = Column(String(255), nullable=False)
    
    # Relationships
    account = relationship("Account", back_populates="partners")
    calls = relationship("Call", back_populates="partner", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Partner(id={self.id}, name={self.name}, kind={self.kind})>"

