"""
Metrics endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, case
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_account
from app.models.call import Call, CallDisposition
from app.models.user import User
from app.schemas.metrics import MetricsSummary, TimeSeriesPoint, TimeSeriesResponse
import uuid

router = APIRouter()


@router.get("/summary", response_model=MetricsSummary)
async def get_metrics_summary(
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    partner_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get KPI summary metrics"""
    query = select(Call).where(Call.account_id == uuid.UUID(account_id))
    
    # Date filters
    if from_date:
        query = query.where(Call.started_at >= from_date)
    if to_date:
        query = query.where(Call.started_at <= to_date)
    else:
        # Default to last 30 days if no to_date
        if not from_date:
            query = query.where(Call.started_at >= datetime.utcnow() - timedelta(days=30))
    
    # Partner filter
    if partner_id:
        query = query.where(Call.partner_id == uuid.UUID(partner_id))
    
    result = await db.execute(query)
    calls = result.scalars().all()
    
    total_calls = len(calls)
    billable_calls = sum(1 for c in calls if c.billable)
    sales = sum(1 for c in calls if c.sale_made)
    connected = sum(1 for c in calls if c.disposition == CallDisposition.CONNECTED)
    
    # Calculate metrics
    closing_percentage = (sales / billable_calls * 100) if billable_calls > 0 else 0.0
    answer_rate = (connected / total_calls * 100) if total_calls > 0 else 0.0
    
    # AOV (Average Order Value)
    sale_amounts = [c.sale_amount_cents for c in calls if c.sale_made and c.sale_amount_cents]
    aov_cents = int(sum(sale_amounts) / len(sale_amounts)) if sale_amounts else None
    
    return MetricsSummary(
        total_calls=total_calls,
        billable_calls=billable_calls,
        sales=sales,
        closing_percentage=round(closing_percentage, 2),
        answer_rate=round(answer_rate, 2),
        aov_cents=aov_cents,
    )


@router.get("/timeseries", response_model=TimeSeriesResponse)
async def get_timeseries(
    interval: str = Query("hour", regex="^(hour|day)$"),
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    partner_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get time series data for charts"""
    from app.models.call_metrics_hourly import CallMetricsHourly
    
    # Default date range: last 30 days
    if not from_date:
        from_date = datetime.utcnow() - timedelta(days=30)
    if not to_date:
        to_date = datetime.utcnow()
    
    # Round to interval boundaries
    if interval == "hour":
        from_date = from_date.replace(minute=0, second=0, microsecond=0)
        to_date = to_date.replace(minute=0, second=0, microsecond=0)
    else:  # day
        from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = select(CallMetricsHourly).where(
        and_(
            CallMetricsHourly.account_id == uuid.UUID(account_id),
            CallMetricsHourly.bucket_start >= from_date,
            CallMetricsHourly.bucket_start <= to_date,
        )
    )
    
    if partner_id:
        query = query.where(CallMetricsHourly.partner_id == uuid.UUID(partner_id))
    
    if interval == "day":
        # Aggregate hourly buckets into daily
        query = query.order_by(CallMetricsHourly.bucket_start)
    
    result = await db.execute(query)
    metrics = result.scalars().all()
    
    # Aggregate by day if needed
    if interval == "day":
        daily_metrics = {}
        for m in metrics:
            day_start = m.bucket_start.replace(hour=0, minute=0, second=0, microsecond=0)
            if day_start not in daily_metrics:
                daily_metrics[day_start] = {
                    "total_calls": 0,
                    "billable_calls": 0,
                    "sales": 0,
                    "connected": 0,
                }
            daily_metrics[day_start]["total_calls"] += m.total_calls
            daily_metrics[day_start]["billable_calls"] += m.billable_calls
            daily_metrics[day_start]["sales"] += m.sales
            daily_metrics[day_start]["connected"] += m.connected
        
        points = [
            TimeSeriesPoint(
                timestamp=timestamp,
                total_calls=data["total_calls"],
                billable_calls=data["billable_calls"],
                sales=data["sales"],
                connected=data["connected"],
            )
            for timestamp, data in sorted(daily_metrics.items())
        ]
    else:
        points = [
            TimeSeriesPoint(
                timestamp=m.bucket_start,
                total_calls=m.total_calls,
                billable_calls=m.billable_calls,
                sales=m.sales,
                connected=m.connected,
            )
            for m in sorted(metrics, key=lambda x: x.bucket_start)
        ]
    
    return TimeSeriesResponse(interval=interval, points=points)

