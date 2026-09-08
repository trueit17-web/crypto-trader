from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from app.core.database import get_db
from app.core.models import ParsedSignal, SignalScore, RawMessage, TelegramSource
from app.api.v1.deps import get_current_user

router = APIRouter(prefix='/signals', tags=['signals'])


class SignalOut(BaseModel):
    id: str
    symbol: str
    direction: str
    entry_min: Optional[float]
    entry_max: Optional[float]
    stop_loss: Optional[float]
    take_profits: list
    leverage: Optional[int]
    confidence: dict
    parsed_at: datetime
    decision: Optional[str]
    final_score: Optional[float]


class SourceOut(BaseModel):
    id: str
    name: str
    channel_id: int
    quality_score: float
    signal_count: int
    win_rate: float
    is_authorized: bool
    is_paper_only: bool


@router.get('/', response_model=List[SignalOut])
async def list_signals(
    limit: int = Query(50, le=200),
    decision: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    q = select(ParsedSignal, SignalScore.decision, SignalScore.final_score).outerjoin(
        SignalScore, SignalScore.parsed_signal_id == ParsedSignal.id
    ).order_by(desc(ParsedSignal.parsed_at)).limit(limit)
    if decision:
        q = q.where(SignalScore.decision == decision)
    result = await db.execute(q)
    rows = result.all()
    return [
        SignalOut(
            id=s.id, symbol=s.symbol, direction=s.direction,
            entry_min=float(s.entry_min) if s.entry_min else None,
            entry_max=float(s.entry_max) if s.entry_max else None,
            stop_loss=float(s.stop_loss) if s.stop_loss else None,
            take_profits=s.take_profits or [],
            leverage=s.leverage,
            confidence=s.confidence or {},
            parsed_at=s.parsed_at,
            decision=dec,
            final_score=float(score) if score else None,
        ) for s, dec, score in rows
    ]


@router.get('/sources', response_model=List[SourceOut])
async def list_sources(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TelegramSource).order_by(desc(TelegramSource.quality_score))
    )
    sources = result.scalars().all()
    return [
        SourceOut(
            id=s.id, name=s.name, channel_id=s.channel_id,
            quality_score=float(s.quality_score),
            signal_count=s.signal_count,
            win_rate=float(s.win_rate),
            is_authorized=s.is_authorized,
            is_paper_only=s.is_paper_only,
        ) for s in sources
    ]


@router.get('/leaderboard', response_model=List[SourceOut])
async def leaderboard(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(TelegramSource)
        .where(TelegramSource.signal_count > 0)
        .order_by(desc(TelegramSource.win_rate))
        .limit(20)
    )
    sources = result.scalars().all()
    return [
        SourceOut(
            id=s.id, name=s.name, channel_id=s.channel_id,
            quality_score=float(s.quality_score),
            signal_count=s.signal_count,
            win_rate=float(s.win_rate),
            is_authorized=s.is_authorized,
            is_paper_only=s.is_paper_only,
        ) for s in sources
    ]
