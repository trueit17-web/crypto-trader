from fastapi import APIRouter

router = APIRouter()


@router.get('/ping')
async def ping():
    return {'pong': True}


# Future routers registered here:
# from app.auth.router import router as auth_router
# from app.signal.router import router as signal_router
# from app.order.router import router as order_router
# from app.portfolio.router import router as portfolio_router
# from app.risk.router import router as risk_router
# router.include_router(auth_router, prefix='/auth', tags=['auth'])
# router.include_router(signal_router, prefix='/signals', tags=['signals'])
# router.include_router(order_router, prefix='/orders', tags=['orders'])
# router.include_router(portfolio_router, prefix='/portfolio', tags=['portfolio'])
# router.include_router(risk_router, prefix='/risk', tags=['risk'])
