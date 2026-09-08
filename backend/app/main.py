"""CryptoTrader Platform — FastAPI application entrypoint."""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.redis_client import init_redis, close_redis
from app.core.database import engine, Base

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
log = structlog.get_logger()

FRONTEND_DIR = Path(__file__).parent.parent.parent / 'frontend'


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info('startup', env=settings.ENVIRONMENT)
    await init_redis()
    log.info('redis_connected')
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
    docs_url='/docs',
    redoc_url='/redoc',
    lifespan=lifespan,
)

# CORS — allow everything (restrict in production via CORS_ORIGINS env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Prometheus
metrics_app = make_asgi_app()
app.mount('/metrics', metrics_app)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from app.api.v1 import router as api_v1_router  # noqa
app.include_router(api_v1_router, prefix='/api/v1')


# ---------------------------------------------------------------------------
# Health & Dashboard
# ---------------------------------------------------------------------------
@app.get('/health')
async def health():
    return {'status': 'ok', 'version': settings.APP_VERSION}


@app.get('/', response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    """Serve the frontend dashboard."""
    html_file = FRONTEND_DIR / 'dashboard.html'
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding='utf-8'))
    return HTMLResponse(content='<h1>CryptoTrader API</h1><p><a href="/docs">API Docs</a></p>')
