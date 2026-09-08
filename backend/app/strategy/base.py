"""BaseStrategy ABC (Section E of spec)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StrategySignal:
    symbol: str
    direction: str          # long | short | close
    confidence: float       # 0.0–1.0
    entry_price: Optional[float]
    stop_loss: float
    take_profits: list[float] = field(default_factory=list)
    size_fraction: float = 1.0  # fraction of max_position_size
    strategy_id: str = ''
    reasoning: dict = field(default_factory=dict)
    expiry_seconds: int = 3600


class BaseStrategy(ABC):
    def __init__(self, config: dict, risk_engine=None, market_data=None):
        self.config = config
        self.risk_engine = risk_engine
        self.market_data = market_data
        self.is_enabled = True

    @abstractmethod
    async def on_bar(self, symbol: str, timeframe: str, bar: dict) -> Optional[StrategySignal]:
        """Called on each new closed candle. bar = {timestamp, open, high, low, close, volume}"""
        ...

    async def on_tick(self, symbol: str, price: float) -> Optional[StrategySignal]:
        """Optional: called on each price tick."""
        return None

    @abstractmethod
    def get_required_symbols(self) -> list[str]: ...

    @abstractmethod
    def get_required_timeframes(self) -> list[str]: ...

    @abstractmethod
    def validate_config(self) -> bool: ...

    @abstractmethod
    def get_regime_filter(self) -> dict:
        """Conditions under which this strategy should be disabled."""
        ...
