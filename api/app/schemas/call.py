"""
Call schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.call import CallDisposition


class CallCreate(BaseModel):
    """Call creation schema"""
    external_call_id: Optional[str] = None
    partner_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    disposition: CallDisposition
    billable: bool = False
    sale_made: bool = False
    sale_amount_cents: Optional[int] = None
    ani: Optional[str] = None
    dnis: Optional[str] = None
    agent_name: Optional[str] = None


class TranscriptData(BaseModel):
    """Transcript data schema"""
    language: str = "en"
    text: str
    words_json: Optional[dict] = None


class SummaryData(BaseModel):
    """Summary data schema"""
    summary: str
    key_points: Optional[List[str]] = None
    sentiment: Optional[str] = None  # "pos", "neu", "neg"


class CallIngestRequest(BaseModel):
    """Call ingestion request (from fefast4.py or webhooks)"""
    external_call_id: str
    partner_id: Optional[str] = None  # UUID or slug
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    disposition: CallDisposition
    billable: bool = False
    sale_made: bool = False
    sale_amount_cents: Optional[int] = None
    ani: Optional[str] = None
    dnis: Optional[str] = None
    agent_name: Optional[str] = None
    transcript: Optional[TranscriptData] = None
    summary: Optional[SummaryData] = None


class CallResponse(BaseModel):
    """Call response schema"""
    id: str
    account_id: str
    partner_id: Optional[str] = None
    external_call_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    disposition: CallDisposition
    billable: bool
    sale_made: bool
    sale_amount_cents: Optional[int] = None
    ani: Optional[str] = None
    dnis: Optional[str] = None
    agent_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CallListResponse(BaseModel):
    """Call list response with pagination"""
    items: List[CallResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

