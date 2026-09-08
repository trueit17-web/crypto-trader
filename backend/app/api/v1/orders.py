from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import uuid, secrets

from app.core.database import get_db
from app.core.models import Order, Exchange
from app.api.v1.deps import get_current_user, require_role

router = APIRouter(prefix='/orders', tags=['orders'])


class OrderOut(BaseModel):
    id: str
    client_order_id: str
    exchange_order_id: Optional[str]
    exchange_id: str
    exchange_name: Optional[str]
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float]
    status: str
    source_type: str
    created_at: datetime
    updated_at: datetime


class CreateOrderIn(BaseModel):
    exchange_id: str
    symbol: str
    side: str         # buy | sell
    order_type: str   # market | limit
    quantity: float
    price: Optional[float] = None


@router.get('/', response_model=List[OrderOut])
async def list_orders(
    limit: int = Query(50, le=500),
    status: Optional[str] = None,
    symbol: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(Order, Exchange.name).outerjoin(Exchange, Order.exchange_id == Exchange.id) \
        .order_by(desc(Order.created_at)).limit(limit)
    if status:
        q = q.where(Order.status == status)
    if symbol:
        q = q.where(Order.symbol == symbol)
    result = await db.execute(q)
    rows = result.all()
    return [
        OrderOut(
            id=o.id, client_order_id=o.client_order_id,
            exchange_order_id=o.exchange_order_id,
            exchange_id=o.exchange_id, exchange_name=name,
            symbol=o.symbol, side=o.side, order_type=o.order_type,
            quantity=float(o.quantity),
            price=float(o.price) if o.price else None,
            status=o.status, source_type=o.source_type,
            created_at=o.created_at, updated_at=o.updated_at,
        ) for o, name in rows
    ]


@router.post('/', response_model=OrderOut, status_code=201)
async def create_order(
    body: CreateOrderIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role('trader', 'admin')),
):
    order = Order(
        client_order_id=f'manual-{secrets.token_hex(8)}',
        exchange_id=body.exchange_id,
        symbol=body.symbol,
        side=body.side,
        order_type=body.order_type,
        quantity=Decimal(str(body.quantity)),
        price=Decimal(str(body.price)) if body.price else None,
        status='pending',
        source_type='manual',
        idempotency_key=secrets.token_hex(16),
    )
    db.add(order)
    await db.flush()
    await db.refresh(order)
    return OrderOut(
        id=order.id, client_order_id=order.client_order_id,
        exchange_order_id=None, exchange_id=order.exchange_id, exchange_name=None,
        symbol=order.symbol, side=order.side, order_type=order.order_type,
        quantity=float(order.quantity),
        price=float(order.price) if order.price else None,
        status=order.status, source_type=order.source_type,
        created_at=order.created_at, updated_at=order.updated_at,
    )
