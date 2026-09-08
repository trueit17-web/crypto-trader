"""ExchangeManager — registry for all active adapters."""
import asyncio
import logging
from typing import Optional

from app.exchange.base import ExchangeAdapter
from app.exchange.binance import BinanceAdapter
from app.exchange.bybit import BybitAdapter

logger = logging.getLogger(__name__)

ADAPTER_REGISTRY: dict[str, type[ExchangeAdapter]] = {
    'binance': BinanceAdapter,
    'bybit':   BybitAdapter,
    # 'kucoin': KuCoinAdapter,  # TICK-future
    # 'okx':    OkxAdapter,
    # 'bingx':  BingxAdapter,
    # 'bitget': BitgetAdapter,
    # 'bitmex': BitMexAdapter,
    # 'hyperliquid': HyperliquidAdapter,
}


class ExchangeManager:
    """Creates, starts, and tracks all exchange adapters."""

    def __init__(self):
        self._adapters: dict[str, ExchangeAdapter] = {}  # exchange_id -> adapter

    def register(
        self,
        exchange_id: str,
        exchange_name: str,
        credentials: dict,
        config: dict,
    ) -> ExchangeAdapter:
        adapter_cls = ADAPTER_REGISTRY.get(exchange_name.lower())
        if not adapter_cls:
            raise ValueError(f'No adapter registered for exchange: {exchange_name}')
        adapter = adapter_cls(credentials, config)
        self._adapters[exchange_id] = adapter
        return adapter

    async def connect_all(self) -> None:
        tasks = [a.connect() for a in self._adapters.values() if not a.is_connected]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def disconnect_all(self) -> None:
        tasks = [a.disconnect() for a in self._adapters.values() if a.is_connected]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get(self, exchange_id: str) -> Optional[ExchangeAdapter]:
        return self._adapters.get(exchange_id)

    def all_adapters(self) -> list[ExchangeAdapter]:
        return list(self._adapters.values())

    async def cancel_all_orders_everywhere(self) -> dict[str, list[str]]:
        """Emergency: cancel all open orders on all exchanges."""
        results = {}
        for eid, adapter in self._adapters.items():
            try:
                cancelled = await adapter.cancel_all_orders()
                results[eid] = cancelled
                logger.info('Cancelled %d orders on %s', len(cancelled), eid)
            except Exception as exc:
                logger.error('Failed to cancel orders on %s: %s', eid, exc)
                results[eid] = []
        return results


# Singleton
exchange_manager = ExchangeManager()
