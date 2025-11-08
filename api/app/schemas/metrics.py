"""
Metrics schemas
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class MetricsSummary(BaseModel):
    """KPI summary metrics"""
    total_calls: int
    billable_calls: int
    sales: int
    closing_percentage: float  # sales / billable_calls
    answer_rate: float  # connected / total_calls
    aov_cents: Optional[int] = None  # Average order value in cents


class TimeSeriesPoint(BaseModel):
    """Time series data point"""
    timestamp: datetime
    total_calls: int
    billable_calls: int
    sales: int
    connected: int


class TimeSeriesResponse(BaseModel):
    """Time series response"""
    interval: str  # "hour" or "day"
    points: List[TimeSeriesPoint]

