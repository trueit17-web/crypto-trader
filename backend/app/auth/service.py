"""Authentication service: JWT + TOTP."""
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import hashlib

from jose import JWTError, jwt
import bcrypt
import pyotp

from app.core.config import settings


def hash_password(plain: str) -> str:
    # bcrypt has 72-byte limit; pre-hash with sha256 to support any length
    key = hashlib.sha256(plain.encode()).hexdigest().encode()
    return bcrypt.hashpw(key, bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    key = hashlib.sha256(plain.encode()).hexdigest().encode()
    try:
        return bcrypt.checkpw(key, hashed.encode())
    except Exception:
        return False


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
    """Returns (token, token_hash)."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        'sub': user_id,
        'exp': expire,
        'type': 'refresh',
        'jti': secrets.token_hex(8),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, hash_token(token)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
