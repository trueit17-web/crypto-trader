"""Risk Engine — multi-level hard limit checks (Section F of spec)."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
import logging

from app.core.config import settings
from app.core.redis_client import is_emergency_shutdown

logger = logging.getLogger(__name__)


class RiskCheckResult(Enum):
    PASS         = 'pass'
    REJECT       = 'reject'
    REDUCE_SIZE  = 'reduce_size'


@dataclass
class RiskCheckOutcome:
    result: RiskCheckResult
    reason: str
    allowed_size_fraction: float  # 0.0 – 1.0


class RiskEngine:
    """
    Pre-order risk checks.
    Returns (RiskCheckResult, reason, allowed_size_fraction).
    Higher layers (portfolio, exchange, asset) evaluated in order;
    first hard REJECT wins.
    """

    def __init__(self, config: Optional[dict] = None):
        self.cfg = {
            'max_account_risk_per_trade': settings.MAX_ACCOUNT_RISK_PER_TRADE,
            'max_portfolio_exposure':     settings.MAX_PORTFOLIO_EXPOSURE,
            'max_exchange_exposure':      settings.MAX_EXCHANGE_EXPOSURE,
            'max_asset_exposure':         settings.MAX_ASSET_EXPOSURE,
            'max_daily_drawdown':         settings.MAX_DAILY_DRAWDOWN,
            'max_weekly_drawdown':        settings.MAX_WEEKLY_DRAWDOWN,
            'max_leverage':               settings.MAX_LEVERAGE,
            'min_liquidation_distance':   settings.MIN_LIQUIDATION_DISTANCE,
            'max_simultaneous_positions': settings.MAX_SIMULTANEOUS_POSITIONS,
            'max_consecutive_losses':     settings.MAX_CONSECUTIVE_LOSSES,
            'max_slippage_pct':           settings.MAX_SLIPPAGE_PCT,
            **(config or {}),
        }

    async def check_pre_order(
        self,
        *,
        symbol: str,
        side: str,
        notional: Decimal,
        leverage: Optional[int],
        stop_loss_distance_pct: float,
        portfolio_value: Decimal,
        daily_pnl_pct: float,
        weekly_pnl_pct: float,
        current_asset_exposure: Decimal,
        open_position_count: int,
        consecutive_losses: int,
        exchange_id: str,
        current_exchange_exposure: Decimal,
    ) -> RiskCheckOutcome:
        reasons: list[str] = []
        size_fraction = 1.0

        # 0. Emergency shutdown
        shutdown_reason = await is_emergency_shutdown()
        if shutdown_reason:
            return RiskCheckOutcome(RiskCheckResult.REJECT, f'Emergency shutdown: {shutdown_reason}', 0.0)

        # 1. Daily drawdown
        if daily_pnl_pct <= -self.cfg['max_daily_drawdown']:
            return RiskCheckOutcome(RiskCheckResult.REJECT, 'Daily drawdown limit reached', 0.0)

        # 2. Weekly drawdown
        if weekly_pnl_pct <= -self.cfg['max_weekly_drawdown']:
            return RiskCheckOutcome(RiskCheckResult.REJECT, 'Weekly drawdown limit reached', 0.0)

        # 3. Leverage hard limit
        if leverage and leverage > self.cfg['max_leverage']:
            return RiskCheckOutcome(
                RiskCheckResult.REJECT,
                f'Leverage {leverage}x exceeds max {self.cfg["max_leverage"]}x',
                0.0,
            )

        # 4. Liquidation distance
        if leverage and leverage > 0:
            liq_distance = 1.0 / leverage
            if liq_distance < self.cfg['min_liquidation_distance']:
                return RiskCheckOutcome(
                    RiskCheckResult.REJECT,
                    f'Liquidation distance {liq_distance:.1%} < min {self.cfg["min_liquidation_distance"]:.1%}',
                    0.0,
                )

        # 5. Max simultaneous positions
        if open_position_count >= self.cfg['max_simultaneous_positions']:
            return RiskCheckOutcome(RiskCheckResult.REJECT, 'Max simultaneous positions reached', 0.0)

        # 6. Consecutive losses kill-switch
        if consecutive_losses >= self.cfg['max_consecutive_losses']:
            return RiskCheckOutcome(RiskCheckResult.REJECT, f'{consecutive_losses} consecutive losses — kill switch', 0.0)

        # 7. Portfolio exposure
        portfolio_float = float(portfolio_value)
        if portfolio_float > 0:
            max_portfolio = Decimal(str(portfolio_float * self.cfg['max_portfolio_exposure']))
            # Not tracked individually here; caller provides this context.

        # 8. Asset-level exposure
        max_asset = Decimal(str(float(portfolio_value) * self.cfg['max_asset_exposure']))
        if current_asset_exposure + notional > max_asset:
            allowed = max_asset - current_asset_exposure
            if allowed <= 0:
                return RiskCheckOutcome(RiskCheckResult.REJECT, f'Asset {symbol} exposure limit reached', 0.0)
            size_fraction = min(size_fraction, float(allowed / notional))
            reasons.append(f'Asset exposure capped to {size_fraction:.0%}')

        # 9. Exchange-level exposure
        max_exchange = Decimal(str(float(portfolio_value) * self.cfg['max_exchange_exposure']))
        if current_exchange_exposure + notional > max_exchange:
            allowed = max_exchange - current_exchange_exposure
            if allowed <= 0:
                return RiskCheckOutcome(RiskCheckResult.REJECT, f'Exchange {exchange_id} exposure limit reached', 0.0)
            size_fraction = min(size_fraction, float(allowed / notional))
            reasons.append(f'Exchange exposure capped to {size_fraction:.0%}')

        # 10. Stop-loss sanity (> 30% from entry)
        if stop_loss_distance_pct > 0.30:
            return RiskCheckOutcome(
                RiskCheckResult.REJECT,
                f'Stop-loss distance {stop_loss_distance_pct:.1%} exceeds 30% hard gate',
                0.0,
            )

        if size_fraction < 0.10:
            return RiskCheckOutcome(RiskCheckResult.REJECT, 'Reduced size < 10% — not worth executing', 0.0)

        if size_fraction < 1.0:
            return RiskCheckOutcome(RiskCheckResult.REDUCE_SIZE, '; '.join(reasons), size_fraction)

        return RiskCheckOutcome(RiskCheckResult.PASS, 'All checks passed', 1.0)

    @staticmethod
    def calculate_position_size(
        portfolio_value: Decimal,
        risk_fraction: float,
        stop_loss_distance_pct: float,
        volatility_multiplier: float = 1.0,
        signal_confidence: float = 1.0,
        max_position_size: Optional[Decimal] = None,
    ) -> Decimal:
        """
        Volatility-adjusted position sizing.
        size = (portfolio × risk%) / sl%  ÷ vol_mult × confidence
        """
        if stop_loss_distance_pct <= 0:
            return Decimal('0')
        base_risk = portfolio_value * Decimal(str(risk_fraction))
        raw_size = base_risk / Decimal(str(stop_loss_distance_pct))
        vol_adjusted = raw_size / Decimal(str(max(volatility_multiplier, 0.1)))
        confidence_adjusted = vol_adjusted * Decimal(str(signal_confidence))
        if max_position_size:
            return min(confidence_adjusted, max_position_size)
        return confidence_adjusted
