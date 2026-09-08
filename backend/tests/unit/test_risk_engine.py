"""Unit tests for RiskEngine."""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from app.risk.engine import RiskEngine, RiskCheckResult


@pytest.fixture
def engine():
    return RiskEngine()


BASE_KWARGS = dict(
    symbol='BTC/USDT',
    side='buy',
    notional=Decimal('1000'),
    leverage=10,
    stop_loss_distance_pct=0.02,
    portfolio_value=Decimal('100000'),
    daily_pnl_pct=-0.01,
    weekly_pnl_pct=-0.03,
    current_asset_exposure=Decimal('0'),
    open_position_count=0,
    consecutive_losses=0,
    exchange_id='exc-1',
    current_exchange_exposure=Decimal('0'),
)


@pytest.mark.asyncio
async def test_pass_all_checks(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**BASE_KWARGS)
    assert outcome.result == RiskCheckResult.PASS
    assert outcome.allowed_size_fraction == 1.0


@pytest.mark.asyncio
async def test_emergency_shutdown_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value='manual stop'):
        outcome = await engine.check_pre_order(**BASE_KWARGS)
    assert outcome.result == RiskCheckResult.REJECT
    assert 'Emergency' in outcome.reason


@pytest.mark.asyncio
async def test_daily_drawdown_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{**BASE_KWARGS, 'daily_pnl_pct': -0.06})
    assert outcome.result == RiskCheckResult.REJECT
    assert 'Daily drawdown' in outcome.reason


@pytest.mark.asyncio
async def test_leverage_exceeds_max_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{**BASE_KWARGS, 'leverage': 20})
    assert outcome.result == RiskCheckResult.REJECT
    assert 'Leverage' in outcome.reason


@pytest.mark.asyncio
async def test_sl_too_wide_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{**BASE_KWARGS, 'stop_loss_distance_pct': 0.35})
    assert outcome.result == RiskCheckResult.REJECT
    assert 'Stop-loss distance' in outcome.reason


@pytest.mark.asyncio
async def test_asset_exposure_reduces_size(engine):
    # Already at 14% exposure, limit is 15%, notional = 5000 -> should reduce
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{
            **BASE_KWARGS,
            'notional': Decimal('5000'),
            'current_asset_exposure': Decimal('14000'),  # 14% already used
        })
    assert outcome.result == RiskCheckResult.REDUCE_SIZE
    assert 0 < outcome.allowed_size_fraction < 1.0


@pytest.mark.asyncio
async def test_max_positions_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{**BASE_KWARGS, 'open_position_count': 20})
    assert outcome.result == RiskCheckResult.REJECT


@pytest.mark.asyncio
async def test_consecutive_losses_rejects(engine):
    with patch('app.risk.engine.is_emergency_shutdown', new_callable=AsyncMock, return_value=None):
        outcome = await engine.check_pre_order(**{**BASE_KWARGS, 'consecutive_losses': 5})
    assert outcome.result == RiskCheckResult.REJECT


def test_position_sizing():
    size = RiskEngine.calculate_position_size(
        portfolio_value=Decimal('100000'),
        risk_fraction=0.01,
        stop_loss_distance_pct=0.02,
        volatility_multiplier=1.0,
        signal_confidence=1.0,
    )
    # 100000 * 0.01 / 0.02 = 50000
    assert size == Decimal('50000')


def test_position_sizing_with_vol_adj():
    size = RiskEngine.calculate_position_size(
        portfolio_value=Decimal('100000'),
        risk_fraction=0.01,
        stop_loss_distance_pct=0.02,
        volatility_multiplier=2.0,   # High vol -> halved
        signal_confidence=0.8,
    )
    # 50000 / 2.0 * 0.8 = 20000
    assert size == Decimal('20000')
