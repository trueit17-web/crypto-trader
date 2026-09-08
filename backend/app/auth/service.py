"""Authentication service: JWT + TOTP (Section I of spec)."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
import pyotp

from app.core.config import settings

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        'sub': user_id,
        'role': role,
        'exp': expire,
        'type': 'access',
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (raw_token, hashed_token)."""
    raw = secrets.token_urlsafe(48)
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        'sub': user_id,
        'exp': expire,
        'type': 'refresh',
        'jti': raw[:8],  # just for uniqueness
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    # Store hash in DB
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_token(token: str) -> str:
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()
