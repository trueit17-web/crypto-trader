from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.models import User, Session
from app.core.config import settings
from app.auth.service import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token, hash_token
)
from app.api.v1.deps import get_current_user

router = APIRouter(prefix='/auth', tags=['auth'])


class RegisterIn(BaseModel):
    email: str
    password: str

class LoginIn(BaseModel):
    email: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'

class RefreshIn(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


@router.post('/register', response_model=UserOut, status_code=201)
async def register(body: RegisterIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, 'Email already registered')
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role='admin',  # первый пользователь = admin
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserOut(id=user.id, email=user.email, role=user.role,
                   is_active=user.is_active, created_at=user.created_at)


@router.post('/login', response_model=TokenOut)
async def login(body: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, 'Invalid credentials')
    if not user.is_active:
        raise HTTPException(403, 'Account disabled')

    access = create_access_token(user.id, user.role)
    refresh, refresh_hash = create_refresh_token(user.id)

    session = Session(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post('/refresh', response_model=TokenOut)
async def refresh(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get('type') != 'refresh':
            raise ValueError
        user_id = payload['sub']
    except Exception:
        raise HTTPException(401, 'Invalid refresh token')

    token_hash = hash_token(body.refresh_token)
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.refresh_token_hash == token_hash,
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(401, 'Session expired or not found')

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, 'User not found')

    access = create_access_token(user.id, user.role)
    refresh_new, refresh_hash_new = create_refresh_token(user.id)
    session.refresh_token_hash = refresh_hash_new
    session.expires_at = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    return TokenOut(access_token=access, refresh_token=refresh_new)


@router.get('/me', response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, role=user.role,
                   is_active=user.is_active, created_at=user.created_at)


@router.post('/logout')
async def logout(body: RefreshIn, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        token_hash = hash_token(body.refresh_token)
        await db.execute(
            Session.__table__.delete().where(
                Session.user_id == payload['sub'],
                Session.refresh_token_hash == token_hash,
            )
        )
    except Exception:
        pass
    return {'ok': True}
