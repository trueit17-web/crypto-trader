from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.signals import router as signals_router
from app.api.v1.orders import router as orders_router
from app.api.v1.exchanges import router as exchanges_router
from app.api.v1.risk import router as risk_router

router = APIRouter()


@router.get('/ping')
async def ping():
    return {'pong': True}


router.include_router(auth_router)
router.include_router(portfolio_router)
router.include_router(signals_router)
router.include_router(orders_router)
router.include_router(exchanges_router)
router.include_router(risk_router)
