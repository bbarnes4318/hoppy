"""
Call metrics hourly aggregation model
"""
from sqlalchemy import Column, ForeignKey, Integer, DateTime, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class CallMetricsHourly(Base):
    """Hourly aggregated call metrics"""
    __tablename__ = "call_metrics_hourly"
    
    bucket_start = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, primary_key=True)
    partner_id = Column(UUID(as_uuid=True), ForeignKey("partners.id"), nullable=True, primary_key=True)
    
    total_calls = Column(Integer, nullable=False, default=0)
    billable_calls = Column(Integer, nullable=False, default=0)
    sales = Column(Integer, nullable=False, default=0)
    answers = Column(Integer, nullable=False, default=0)
    connected = Column(Integer, nullable=False, default=0)
    unique_callers = Column(Integer, nullable=False, default=0)
    
    __table_args__ = (
        PrimaryKeyConstraint("bucket_start", "account_id", "partner_id"),
        {},
    )
    
    def __repr__(self):
        return f"<CallMetricsHourly(bucket_start={self.bucket_start}, total_calls={self.total_calls})>"

