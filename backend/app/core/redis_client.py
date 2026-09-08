"""Redis connection pool and helper utilities."""
import json
from contextlib import asynccontextmanager
from typing import Any, Optional

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

# Three separate logical databases
_cache_pool: Optional[Redis] = None
_queue_pool: Optional[Redis] = None
_ratelimit_pool: Optional[Redis] = None


def _make_url(db: int) -> str:
    return f'redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{db}'


async def init_redis() -> None:
    global _cache_pool, _queue_pool, _ratelimit_pool
    _cache_pool    = await aioredis.from_url(_make_url(settings.REDIS_DB_CACHE),    decode_responses=True)
    _queue_pool    = await aioredis.from_url(_make_url(settings.REDIS_DB_QUEUE),    decode_responses=True)
    _ratelimit_pool= await aioredis.from_url(_make_url(settings.REDIS_DB_RATELIMIT), decode_responses=True)


async def close_redis() -> None:
    for pool in (_cache_pool, _queue_pool, _ratelimit_pool):
        if pool:
            await pool.aclose()


def cache() -> Redis:
    assert _cache_pool, 'Redis not initialised — call init_redis() first'
    return _cache_pool


def queue() -> Redis:
    assert _queue_pool, 'Redis not initialised — call init_redis() first'
    return _queue_pool


def ratelimit() -> Redis:
    assert _ratelimit_pool, 'Redis not initialised — call init_redis() first'
    return _ratelimit_pool


# --------------------------------------------------------------------------
# Distributed lock
# --------------------------------------------------------------------------
@asynccontextmanager
async def redis_lock(key: str, timeout: int = 30):
    """Simple Redis SETNX-based distributed lock."""
    import asyncio
    r = cache()
    acquired = False
    try:
        while not acquired:
            acquired = await r.set(f'lock:{key}', '1', ex=timeout, nx=True)
            if not acquired:
                await asyncio.sleep(0.05)
        yield
    finally:
        if acquired:
            await r.delete(f'lock:{key}')


# --------------------------------------------------------------------------
# Emergency shutdown flag
# --------------------------------------------------------------------------
async def set_emergency_shutdown(reason: str) -> None:
    await cache().set('emergency_shutdown', reason, ex=86400)


async def is_emergency_shutdown() -> Optional[str]:
    return await cache().get('emergency_shutdown')


async def clear_emergency_shutdown() -> None:
    await cache().delete('emergency_shutdown')
