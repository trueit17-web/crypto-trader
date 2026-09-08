from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
import base64

from app.core.database import get_db
from app.core.models import Exchange, ExchangeCredential
from app.api.v1.deps import get_current_user, require_role

router = APIRouter(prefix='/exchanges', tags=['exchanges'])


class ExchangeOut(BaseModel):
    id: str
    name: str
    adapter_class: str
    is_active: bool
    created_at: datetime


class ExchangeCreate(BaseModel):
    name: str
    adapter_class: str  # binance | bybit | okx | ...


class CredentialIn(BaseModel):
    exchange_id: str
    api_key: str
    api_secret: str


class CredentialOut(BaseModel):
    id: str
    exchange_id: str
    exchange_name: Optional[str]
    permissions_verified: bool
    created_at: datetime


def simple_encrypt(text: str) -> str:
    """Simple base64 encoding - replace with proper encryption in prod"""
    return base64.b64encode(text.encode()).decode()


@router.get('/', response_model=List[ExchangeOut])
async def list_exchanges(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Exchange).order_by(Exchange.name))
    exchanges = result.scalars().all()
    return [
        ExchangeOut(id=e.id, name=e.name, adapter_class=e.adapter_class,
                    is_active=e.is_active, created_at=e.created_at)
        for e in exchanges
    ]


@router.post('/', response_model=ExchangeOut, status_code=201)
async def create_exchange(
    body: ExchangeCreate,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role('admin')),
):
    existing = await db.execute(select(Exchange).where(Exchange.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f'Exchange {body.name} already exists')
    exchange = Exchange(name=body.name, adapter_class=body.adapter_class)
    db.add(exchange)
    await db.flush()
    await db.refresh(exchange)
    return ExchangeOut(id=exchange.id, name=exchange.name,
                       adapter_class=exchange.adapter_class,
                       is_active=exchange.is_active, created_at=exchange.created_at)


@router.post('/credentials', response_model=CredentialOut, status_code=201)
async def add_credentials(
    body: CredentialIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    exchange = await db.get(Exchange, body.exchange_id)
    if not exchange:
        raise HTTPException(404, 'Exchange not found')
    cred = ExchangeCredential(
        user_id=user.id,
        exchange_id=body.exchange_id,
        encrypted_api_key=simple_encrypt(body.api_key),
        encrypted_secret=simple_encrypt(body.api_secret),
    )
    db.add(cred)
    await db.flush()
    await db.refresh(cred)
    return CredentialOut(
        id=cred.id, exchange_id=cred.exchange_id,
        exchange_name=exchange.name,
        permissions_verified=cred.permissions_verified,
        created_at=cred.created_at,
    )


@router.get('/credentials', response_model=List[CredentialOut])
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(ExchangeCredential, Exchange.name)
        .join(Exchange, ExchangeCredential.exchange_id == Exchange.id)
        .where(ExchangeCredential.user_id == user.id)
    )
    rows = result.all()
    return [
        CredentialOut(
            id=c.id, exchange_id=c.exchange_id, exchange_name=name,
            permissions_verified=c.permissions_verified, created_at=c.created_at,
        ) for c, name in rows
    ]
