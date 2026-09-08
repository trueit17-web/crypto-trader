"""EMA Crossover + ADX trend-following strategy (Section E of spec)."""
from typing import Optional
from collections import deque
import logging

from app.strategy.base import BaseStrategy, StrategySignal

logger = logging.getLogger(__name__)


def _ema(values: list[float], period: int) -> float:
    """Exponential Moving Average."""
    k = 2 / (period + 1)
    result = values[0]
    for v in values[1:]:
        result = v * k + result * (1 - k)
    return result


def _atr(bars: list[dict], period: int = 14) -> float:
    """Average True Range."""
    trs = []
    for i in range(1, len(bars)):
        h = bars[i]['high']
        l = bars[i]['low']
        pc = bars[i-1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    return sum(trs[-period:]) / min(len(trs), period)


class EMACrossoverStrategy(BaseStrategy):
    """
    Trend-following: EMA(20) crosses above EMA(50).
    Stop = 2×ATR(14) below entry.
    TP1 = 3×ATR, TP2 = 5×ATR.
    Disabled when ADX < 20 on daily (regime filter).
    """

    def __init__(self, config: dict, **kwargs):
        super().__init__(config, **kwargs)
        self.fast = config.get('ema_fast', 20)
        self.slow = config.get('ema_slow', 50)
        self.atr_period = config.get('atr_period', 14)
        self.sl_atr_mult = config.get('sl_atr_mult', 2.0)
        self.tp1_atr_mult = config.get('tp1_atr_mult', 3.0)
        self.tp2_atr_mult = config.get('tp2_atr_mult', 5.0)
        self._bars: deque = deque(maxlen=max(self.slow + 1, 60))
        self._prev_cross: Optional[str] = None  # 'above' | 'below'

    def validate_config(self) -> bool:
        return self.fast < self.slow

    def get_required_symbols(self) -> list[str]:
        return self.config.get('symbols', ['BTC/USDT'])

    def get_required_timeframes(self) -> list[str]:
        return ['4h']

    def get_regime_filter(self) -> dict:
        return {'adx_min': 20, 'timeframe': '1d'}

    async def on_bar(self, symbol: str, timeframe: str, bar: dict) -> Optional[StrategySignal]:
        self._bars.append(bar)
        bars = list(self._bars)

        if len(bars) < self.slow + 1:
            return None  # warmup

        closes = [b['close'] for b in bars]
        ema_fast = _ema(closes[-self.fast:], self.fast)
        ema_slow = _ema(closes[-self.slow:], self.slow)
        prev_closes = [b['close'] for b in bars[:-1]]
        prev_fast = _ema(prev_closes[-self.fast:], self.fast)
        prev_slow = _ema(prev_closes[-self.slow:], self.slow)

        atr = _atr(bars, self.atr_period)
        if atr == 0:
            return None

        current_cross = 'above' if ema_fast > ema_slow else 'below'
        prev_cross = 'above' if prev_fast > prev_slow else 'below'

        signal = None

        # Golden cross: fast crosses above slow
        if current_cross == 'above' and prev_cross == 'below':
            entry = bar['close']
            sl = entry - self.sl_atr_mult * atr
            tp1 = entry + self.tp1_atr_mult * atr
            tp2 = entry + self.tp2_atr_mult * atr
            signal = StrategySignal(
                symbol=symbol,
                direction='long',
                confidence=0.7,
                entry_price=entry,
                stop_loss=sl,
                take_profits=[tp1, tp2],
                size_fraction=1.0,
                strategy_id=self.__class__.__name__,
                reasoning={'ema_fast': ema_fast, 'ema_slow': ema_slow, 'atr': atr},
            )
            logger.info('EMA golden cross on %s @ %.2f', symbol, entry)

        # Death cross: fast crosses below slow
        elif current_cross == 'below' and prev_cross == 'above':
            entry = bar['close']
            sl = entry + self.sl_atr_mult * atr
            tp1 = entry - self.tp1_atr_mult * atr
            tp2 = entry - self.tp2_atr_mult * atr
            signal = StrategySignal(
                symbol=symbol,
                direction='short',
                confidence=0.65,
                entry_price=entry,
                stop_loss=sl,
                take_profits=[tp1, tp2],
                size_fraction=0.8,
                strategy_id=self.__class__.__name__,
                reasoning={'ema_fast': ema_fast, 'ema_slow': ema_slow, 'atr': atr},
            )
            logger.info('EMA death cross on %s @ %.2f', symbol, entry)

        self._prev_cross = current_cross
        return signal
