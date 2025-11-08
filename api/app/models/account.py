"""
Account model (tenant)
"""
import uuid
from sqlalchemy import Column, String, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AccountType(str, enum.Enum):
    """Account type enum"""
    PUBLISHER = "publisher"
    AGENCY = "agency"
    BROKER = "broker"
    ADMIN = "admin"


class Account(Base):
    """Account/tenant model"""
    __tablename__ = "accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(SQLEnum(AccountType), nullable=False)
    
    # Relationships
    users = relationship("User", back_populates="account", cascade="all, delete-orphan")
    partners = relationship("Partner", back_populates="account", cascade="all, delete-orphan")
    calls = relationship("Call", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(id={self.id}, name={self.name}, slug={self.slug})>"

