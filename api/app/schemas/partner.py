"""
Partner schemas
"""
from pydantic import BaseModel
from typing import List
from app.models.partner import PartnerKind


class PartnerResponse(BaseModel):
    """Partner response schema"""
    id: str
    account_id: str
    kind: PartnerKind
    name: str
    
    class Config:
        from_attributes = True


class PartnerListResponse(BaseModel):
    """Partner list response"""
    items: List[PartnerResponse]

