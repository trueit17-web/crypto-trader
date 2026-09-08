from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from app.core.database import get_db
from app.core.models import Balance, Position, PortfolioSnapshot, Exchange
from app.api.v1.deps import get_current_user
from app.core.models import User

router = APIRouter(prefix='/portfolio', tags=['portfolio'])


class BalanceOut(BaseModel):
    id: str
    exchange_id: str
    exchange_name: Optional[str]
    currency: str
    total: float
    available: float
    locked: float
    updated_at: datetime


class PositionOut(BaseModel):
    id: str
    exchange_id: str
    exchange_name: Optional[str]
    symbol: str
    side: str
    quantity: float
    entry_price: float
    leverage: int
    margin_mode: str
    unrealized_pnl: float
    liquidation_price: Optional[float]
    opened_at: datetime


class SnapshotOut(BaseModel):
    id: str
    timestamp: datetime
    total_equity: float
    unrealized_pnl: float
    realized_pnl_day: float


class SummaryOut(BaseModel):
    total_equity: float
    unrealized_pnl: float
    realized_pnl_day: float
    open_positions: int
    active_exchanges: int


@router.get('/summary', response_model=SummaryOut)
async def get_summary(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    snap = await db.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.desc()).limit(1)
    )
    snap = snap.scalar_one_or_none()
    positions = await db.execute(select(func.count(Position.id)))
    pos_count = positions.scalar() or 0
    exchanges = await db.execute(select(func.count(Exchange.id)).where(Exchange.is_active == True))
    exc_count = exchanges.scalar() or 0
    return SummaryOut(
        total_equity=float(snap.total_equity) if snap else 0.0,
        unrealized_pnl=float(snap.unrealized_pnl) if snap else 0.0,
        realized_pnl_day=float(snap.realized_pnl_day) if snap else 0.0,
        open_positions=pos_count,
        active_exchanges=exc_count,
    )


@router.get('/balances', response_model=List[BalanceOut])
async def get_balances(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Balance, Exchange.name).join(Exchange, Balance.exchange_id == Exchange.id)
    )
    rows = result.all()
    return [
        BalanceOut(
            id=b.id, exchange_id=b.exchange_id, exchange_name=name,
            currency=b.currency, total=float(b.total),
            available=float(b.available), locked=float(b.locked),
            updated_at=b.updated_at,
        ) for b, name in rows
    ]


@router.get('/positions', response_model=List[PositionOut])
async def get_positions(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(Position, Exchange.name).join(Exchange, Position.exchange_id == Exchange.id)
    )
    rows = result.all()
    return [
        PositionOut(
            id=p.id, exchange_id=p.exchange_id, exchange_name=name,
            symbol=p.symbol, side=p.side,
            quantity=float(p.quantity), entry_price=float(p.entry_price),
            leverage=p.leverage, margin_mode=p.margin_mode,
            unrealized_pnl=float(p.unrealized_pnl),
            liquidation_price=float(p.liquidation_price) if p.liquidation_price else None,
            opened_at=p.opened_at,
        ) for p, name in rows
    ]


@router.get('/snapshots', response_model=List[SnapshotOut])
async def get_snapshots(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user)
):
    result = await db.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.timestamp.desc()).limit(limit)
    )
    snaps = result.scalars().all()
    return [
        SnapshotOut(
            id=s.id, timestamp=s.timestamp,
            total_equity=float(s.total_equity),
            unrealized_pnl=float(s.unrealized_pnl),
            realized_pnl_day=float(s.realized_pnl_day),
        ) for s in snaps
    ]
