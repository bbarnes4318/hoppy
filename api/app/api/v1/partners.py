"""
Partner endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_account
from app.models.partner import Partner
from app.models.user import User
from app.schemas.partner import PartnerResponse, PartnerListResponse
import uuid

router = APIRouter()


@router.get("", response_model=PartnerListResponse)
async def list_partners(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """List all partners for current account"""
    result = await db.execute(
        select(Partner).where(Partner.account_id == uuid.UUID(account_id))
    )
    partners = result.scalars().all()
    
    return PartnerListResponse(
        items=[PartnerResponse.model_validate(p) for p in partners]
    )


@router.get("/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    account_id: str = Depends(get_current_account),
):
    """Get partner by ID"""
    result = await db.execute(
        select(Partner).where(
            and_(
                Partner.id == uuid.UUID(partner_id),
                Partner.account_id == uuid.UUID(account_id),
            )
        )
    )
    partner = result.scalar_one_or_none()
    
    if not partner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partner not found",
        )
    
    return PartnerResponse.model_validate(partner)

