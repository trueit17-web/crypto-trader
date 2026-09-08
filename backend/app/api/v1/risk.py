from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.models import RiskEventModel, RiskConfig
from app.api.v1.deps import get_current_user, require_role

router = APIRouter(prefix='/risk', tags=['risk'])


class RiskEventOut(BaseModel):
    id: str
    event_type: str
    severity: str
    component: Optional[str]
    details: dict
    is_resolved: bool
    created_at: datetime


class RiskConfigOut(BaseModel):
    id: str
    scope: Optional[str]
    scope_id: Optional[str]
    param_name: str
    param_value: str
    updated_at: datetime


class RiskConfigIn(BaseModel):
    scope: str = 'global'
    scope_id: Optional[str] = None
    param_name: str
    param_value: str


@router.get('/events', response_model=List[RiskEventOut])
async def list_events(
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    q = select(RiskEventModel).order_by(desc(RiskEventModel.created_at)).limit(limit)
    if severity:
        q = q.where(RiskEventModel.severity == severity)
    if resolved is not None:
        q = q.where(RiskEventModel.is_resolved == resolved)
    result = await db.execute(q)
    events = result.scalars().all()
    return [
        RiskEventOut(
            id=e.id, event_type=e.event_type, severity=e.severity,
            component=e.component, details=e.details or {},
            is_resolved=e.is_resolved, created_at=e.created_at,
        ) for e in events
    ]


@router.patch('/events/{event_id}/resolve')
async def resolve_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role('trader', 'admin')),
):
    event = await db.get(RiskEventModel, event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(404, 'Event not found')
    event.is_resolved = True
    return {'ok': True}


@router.get('/config', response_model=List[RiskConfigOut])
async def list_config(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(RiskConfig).order_by(RiskConfig.scope, RiskConfig.param_name))
    configs = result.scalars().all()
    return [
        RiskConfigOut(
            id=c.id, scope=c.scope, scope_id=c.scope_id,
            param_name=c.param_name, param_value=c.param_value,
            updated_at=c.updated_at,
        ) for c in configs
    ]


@router.post('/config', response_model=RiskConfigOut, status_code=201)
async def set_config(
    body: RiskConfigIn,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role('admin')),
):
    cfg = RiskConfig(
        scope=body.scope, scope_id=body.scope_id,
        param_name=body.param_name, param_value=body.param_value,
        updated_by=user.id,
    )
    db.add(cfg)
    await db.flush()
    await db.refresh(cfg)
    return RiskConfigOut(
        id=cfg.id, scope=cfg.scope, scope_id=cfg.scope_id,
        param_name=cfg.param_name, param_value=cfg.param_value,
        updated_at=cfg.updated_at,
    )
