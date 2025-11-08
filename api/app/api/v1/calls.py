"""
Call endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_account
from app.models.call import Call
from app.models.partner import Partner
from app.schemas.call import CallResponse, CallListResponse, CallIngestRequest
from app.models.user import User
import uuid

router = APIRouter()


@router.post("/ingest", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def ingest_call(
    data: CallIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """
    Ingest a call from fefast4.py or webhook.
    Validates, stores records, updates metrics, and emits NOTIFY for real-time clients.
    """
    async with db.begin():
        # Resolve partner_id if slug provided
        partner_id = None
        if data.partner_id:
            try:
                # Try as UUID first
                partner_id = uuid.UUID(data.partner_id)
            except ValueError:
                # Try as slug
                result = await db.execute(
                    select(Partner).where(
                        and_(
                            Partner.account_id == uuid.UUID(account_id),
                            Partner.name == data.partner_id,
                        )
                    )
                )
                partner = result.scalar_one_or_none()
                if partner:
                    partner_id = partner.id
        
        # Create/update call
        # Check if call exists by external_call_id
        existing_call = None
        if data.external_call_id:
            result = await db.execute(
                select(Call).where(
                    and_(
                        Call.external_call_id == data.external_call_id,
                        Call.account_id == uuid.UUID(account_id),
                    )
                )
            )
            existing_call = result.scalar_one_or_none()
        
        if existing_call:
            # Update existing call
            call = existing_call
            call.partner_id = partner_id
            call.started_at = data.started_at
            call.ended_at = data.ended_at
            call.duration_sec = data.duration_sec
            call.disposition = data.disposition
            call.billable = data.billable
            call.sale_made = data.sale_made
            call.sale_amount_cents = data.sale_amount_cents
            call.ani = data.ani
            call.dnis = data.dnis
            call.agent_name = data.agent_name
        else:
            # Create new call
            call = Call(
                account_id=uuid.UUID(account_id),
                partner_id=partner_id,
                external_call_id=data.external_call_id,
                started_at=data.started_at,
                ended_at=data.ended_at,
                duration_sec=data.duration_sec,
                disposition=data.disposition,
                billable=data.billable,
                sale_made=data.sale_made,
                sale_amount_cents=data.sale_amount_cents,
                ani=data.ani,
                dnis=data.dnis,
                agent_name=data.agent_name,
            )
            db.add(call)
            await db.flush()
        
        # Create/update transcript
        if data.transcript:
            from app.models.transcript import Transcript
            result = await db.execute(
                select(Transcript).where(Transcript.call_id == call.id)
            )
            transcript = result.scalar_one_or_none()
            
            if transcript:
                transcript.language = data.transcript.language
                transcript.text = data.transcript.text
                transcript.words_json = data.transcript.words_json
            else:
                transcript = Transcript(
                    call_id=call.id,
                    language=data.transcript.language,
                    text=data.transcript.text,
                    words_json=data.transcript.words_json,
                )
                db.add(transcript)
        
        # Create/update summary
        if data.summary:
            from app.models.summary import Summary, Sentiment
            result = await db.execute(
                select(Summary).where(Summary.call_id == call.id)
            )
            summary = result.scalar_one_or_none()
            
            sentiment = None
            if data.summary.sentiment:
                try:
                    sentiment = Sentiment(data.summary.sentiment.lower())
                except ValueError:
                    pass
            
            if summary:
                summary.summary = data.summary.summary
                summary.key_points = data.summary.key_points
                summary.sentiment = sentiment
            else:
                summary = Summary(
                    call_id=call.id,
                    summary=data.summary.summary,
                    key_points=data.summary.key_points,
                    sentiment=sentiment,
                )
                db.add(summary)
        
        # Update metrics hourly bucket
        await update_metrics_hourly(db, call, account_id)
        
        # Emit NOTIFY for real-time clients
        await db.execute(
            text(
                "SELECT pg_notify('hopwhistle_metrics', :payload)"
            ).bindparams(
                payload=f'{{"type":"call_ingested","call_id":"{call.id}","account_id":"{account_id}"}}'
            )
        )
        
        # Broadcast to WebSocket clients (non-blocking)
        try:
            from app.api.v1.websocket import broadcast_metrics_update
            import asyncio
            asyncio.create_task(broadcast_metrics_update({
                "type": "call_ingested",
                "call_id": str(call.id),
                "account_id": account_id,
            }))
        except Exception as e:
            # Don't fail the request if WebSocket broadcast fails
            print(f"WebSocket broadcast error: {e}")
    
    await db.refresh(call)
    return CallResponse.model_validate(call)


async def update_metrics_hourly(db: AsyncSession, call: Call, account_id: str):
    """Update hourly metrics bucket"""
    from app.models.call_metrics_hourly import CallMetricsHourly
    from datetime import timedelta
    
    # Round to hour
    bucket_start = call.started_at.replace(minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(CallMetricsHourly).where(
            and_(
                CallMetricsHourly.bucket_start == bucket_start,
                CallMetricsHourly.account_id == uuid.UUID(account_id),
                CallMetricsHourly.partner_id == call.partner_id,
            )
        )
    )
    metrics = result.scalar_one_or_none()
    
    if metrics:
        metrics.total_calls += 1
        if call.billable:
            metrics.billable_calls += 1
        if call.sale_made:
            metrics.sales += 1
        if call.disposition.value == "connected":
            metrics.connected += 1
            metrics.answers += 1
    else:
        metrics = CallMetricsHourly(
            bucket_start=bucket_start,
            account_id=uuid.UUID(account_id),
            partner_id=call.partner_id,
            total_calls=1,
            billable_calls=1 if call.billable else 0,
            sales=1 if call.sale_made else 0,
            connected=1 if call.disposition.value == "connected" else 0,
            answers=1 if call.disposition.value == "connected" else 0,
            unique_callers=1,  # Simplified - would need deduplication in real implementation
        )
        db.add(metrics)


@router.get("", response_model=CallListResponse)
async def list_calls(
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    partner_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),  # Full-text search
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """List calls with filters and pagination"""
    query = select(Call).where(Call.account_id == uuid.UUID(account_id))
    
    # Date filters
    if from_date:
        query = query.where(Call.started_at >= from_date)
    if to_date:
        query = query.where(Call.started_at <= to_date)
    
    # Partner filter
    if partner_id:
        query = query.where(Call.partner_id == uuid.UUID(partner_id))
    
    # Full-text search
    if q:
        from app.models.transcript import Transcript
        query = query.join(Transcript, Call.id == Transcript.call_id, isouter=True).where(
            or_(
                Call.external_call_id.ilike(f"%{q}%"),
                Call.ani.ilike(f"%{q}%"),
                Call.dnis.ilike(f"%{q}%"),
                Call.agent_name.ilike(f"%{q}%"),
                Transcript.text.ilike(f"%{q}%"),
            )
        )
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Pagination
    query = query.order_by(Call.started_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query)
    calls = result.scalars().all()
    
    return CallListResponse(
        items=[CallResponse.model_validate(call) for call in calls],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get call by ID"""
    result = await db.execute(
        select(Call).where(
            and_(
                Call.id == uuid.UUID(call_id),
                Call.account_id == uuid.UUID(account_id),
            )
        )
    )
    call = result.scalar_one_or_none()
    
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )
    
    return CallResponse.model_validate(call)


@router.get("/{call_id}/transcript")
async def get_call_transcript(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get call transcript"""
    from app.models.transcript import Transcript
    
    result = await db.execute(
        select(Transcript)
        .join(Call, Transcript.call_id == Call.id)
        .where(
            and_(
                Call.id == uuid.UUID(call_id),
                Call.account_id == uuid.UUID(account_id),
            )
        )
    )
    transcript = result.scalar_one_or_none()
    
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )
    
    return {
        "call_id": str(transcript.call_id),
        "language": transcript.language,
        "text": transcript.text,
        "words_json": transcript.words_json,
    }


@router.get("/{call_id}/summary")
async def get_call_summary(
    call_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get call summary"""
    from app.models.summary import Summary
    
    result = await db.execute(
        select(Summary)
        .join(Call, Summary.call_id == Call.id)
        .where(
            and_(
                Call.id == uuid.UUID(call_id),
                Call.account_id == uuid.UUID(account_id),
            )
        )
    )
    summary = result.scalar_one_or_none()
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found",
        )
    
    return {
        "call_id": str(summary.call_id),
        "summary": summary.summary,
        "key_points": summary.key_points,
        "sentiment": summary.sentiment.value if summary.sentiment else None,
    }

