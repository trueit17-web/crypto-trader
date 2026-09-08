"""ExchangeAdapter ABC + supporting dataclasses (Section C of spec)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import AsyncIterator, Optional
import asyncio
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class NormalizedSymbol:
    base: str             # BTC
    quote: str            # USDT
    market_type: str      # spot | perp | margin
    exchange_symbol: str  # native exchange format e.g. BTCUSDT

    def __str__(self) -> str:
        return f'{self.base}/{self.quote}:{self.market_type}'


@dataclass
class OrderRequest:
    client_order_id: str
    symbol: NormalizedSymbol
    side: str              # buy | sell
    order_type: str        # market | limit | stop_market | stop_limit
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = 'GTC'   # GTC | IOC | FOK
    reduce_only: bool = False
    margin_mode: str = 'isolated'
    leverage: Optional[int] = None
    idempotency_key: str = ''


@dataclass
class OrderResult:
    exchange_order_id: str
    client_order_id: str
    status: str             # open | filled | partially_filled | cancelled | rejected
    filled_qty: Decimal
    avg_fill_price: Decimal
    fees: Decimal
    fee_currency: str
    timestamp_ms: int
    raw_response: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """Token bucket with automatic backing off."""

    def __init__(self, requests_per_second: float, burst: int):
        self.rate = requests_per_second
        self.burst = burst
        self.tokens: float = float(burst)
        self._lock = asyncio.Lock()
        self._last_refill = time.monotonic()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._last_refill = now
            self.tokens = min(self.tokens + elapsed * self.rate, self.burst)
            while self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._last_refill = now
                self.tokens = min(self.tokens + elapsed * self.rate, self.burst)
            self.tokens -= 1.0


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
class CircuitBreaker:
    """Auto-disconnects an exchange after repeated failures."""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.state = self.CLOSED
        self.failure_count = 0
        self.threshold = failure_threshold
        self.timeout = timeout_seconds
        self.last_failure_time: Optional[float] = None

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = self.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.threshold:
            self.state = self.OPEN
            logger.warning('CircuitBreaker OPEN after %d failures', self.failure_count)

    def allow_request(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if time.monotonic() - (self.last_failure_time or 0) > self.timeout:
                self.state = self.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one probe
        return True

    @property
    def is_open(self) -> bool:
        return not self.allow_request()


# ---------------------------------------------------------------------------
# Abstract Adapter
# ---------------------------------------------------------------------------
class ExchangeAdapter(ABC):
    """Unified interface for all exchange connectors."""

    def __init__(self, credentials: dict, config: dict):
        self.credentials = credentials
        self.config = config
        self.rate_limiter = RateLimiter(
            requests_per_second=config.get('rps', 10),
            burst=config.get('burst', 20),
        )
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get('cb_threshold', 5),
            timeout_seconds=config.get('cb_timeout', 60),
        )
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_account_info(self) -> dict: ...

    @abstractmethod
    async def get_balances(self) -> dict[str, Decimal]: ...

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    @abstractmethod
    async def place_order(self, req: OrderRequest) -> OrderResult: ...

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool: ...

    @abstractmethod
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> list[str]: ...

    @abstractmethod
    async def get_order_status(self, symbol: str, order_id: str) -> OrderResult: ...

    # ------------------------------------------------------------------
    # Market info
    # ------------------------------------------------------------------
    @abstractmethod
    async def get_instrument_info(self, symbol: str) -> dict: ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 500,
    ) -> list[list]: ...

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    @abstractmethod
    async def subscribe_trades(self, symbols: list[str]) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def subscribe_orderbook(self, symbols: list[str]) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def subscribe_klines(
        self, symbols: list[str], timeframe: str
    ) -> AsyncIterator[dict]: ...

    @abstractmethod
    async def subscribe_user_data(self) -> AsyncIterator[dict]: ...

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------
    @abstractmethod
    async def reconcile_positions(self) -> list[dict]: ...

    # ------------------------------------------------------------------
    # Helper: guarded call with circuit breaker + rate limiter
    # ------------------------------------------------------------------
    async def _call(self, coro):
        if self.circuit_breaker.is_open:
            raise RuntimeError(f'{self.__class__.__name__} circuit breaker is OPEN')
        await self.rate_limiter.acquire()
        try:
            result = await coro
            self.circuit_breaker.record_success()
            return result
        except Exception as exc:
            self.circuit_breaker.record_failure()
            raise
