"""CryptoTrader Platform — FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.redis_client import init_redis, close_redis
from app.core.database import engine, Base

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Lifespan: startup + shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info('startup', env=settings.ENVIRONMENT)
    await init_redis()
    log.info('redis_connected')
    # Create tables in dev (Alembic handles prod)
    if settings.ENVIRONMENT == 'development':
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_redis()
    await engine.dispose()
    log.info('shutdown')


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url='/docs' if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount('/metrics', metrics_app)


# ---------------------------------------------------------------------------
# Routers (imported lazily to avoid circular deps)
# ---------------------------------------------------------------------------
from app.api.v1 import router as api_v1_router  # noqa: E402
app.include_router(api_v1_router, prefix='/api/v1')


@app.get('/health')
async def health():
    return {'status': 'ok', 'version': settings.APP_VERSION}
