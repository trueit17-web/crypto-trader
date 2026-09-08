"""Binance exchange adapter (TICK-005)."""
from decimal import Decimal
from typing import AsyncIterator, Optional
import asyncio
import logging

import ccxt.pro as ccxtpro
import ccxt

from app.exchange.base import ExchangeAdapter, NormalizedSymbol, OrderRequest, OrderResult

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """
    Supports:
        - Spot (binance)
        - USDT-margined Perpetual Futures (binanceusdm)
        - Coin-margined Futures (binancecoinm) — partial
    """

    def __init__(self, credentials: dict, config: dict):
        super().__init__(credentials, config)
        market_type = config.get('market_type', 'spot')  # spot | perp
        exchange_id = 'binanceusdm' if market_type == 'perp' else 'binance'

        self._exchange = getattr(ccxtpro, exchange_id)({
            'apiKey': credentials.get('api_key', ''),
            'secret': credentials.get('api_secret', ''),
            'enableRateLimit': False,  # we handle rate limiting ourselves
            'options': {
                'defaultType': 'future' if market_type == 'perp' else 'spot',
            },
        })
        # Use testnet if configured
        if config.get('testnet', False):
            self._exchange.set_sandbox_mode(True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        await self._exchange.load_markets()
        self._connected = True
        logger.info('BinanceAdapter connected')

    async def disconnect(self) -> None:
        await self._exchange.close()
        self._connected = False
        logger.info('BinanceAdapter disconnected')

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    async def get_account_info(self) -> dict:
        return await self._call(self._exchange.fetch_status())

    async def get_balances(self) -> dict[str, Decimal]:
        raw = await self._call(self._exchange.fetch_balance())
        return {
            currency: Decimal(str(info['total']))
            for currency, info in raw.items()
            if isinstance(info, dict) and info.get('total', 0) > 0
        }

    async def get_positions(self) -> list[dict]:
        try:
            positions = await self._call(self._exchange.fetch_positions())
            return [
                {
                    'symbol': p['symbol'],
                    'side': p['side'],
                    'quantity': Decimal(str(p['contracts'] or 0)),
                    'entry_price': Decimal(str(p['entryPrice'] or 0)),
                    'unrealized_pnl': Decimal(str(p['unrealizedPnl'] or 0)),
                    'leverage': int(p.get('leverage') or 1),
                    'margin_mode': p.get('marginMode', 'isolated'),
                    'liquidation_price': Decimal(str(p.get('liquidationPrice') or 0)),
                }
                for p in positions
                if (p.get('contracts') or 0) != 0
            ]
        except ccxt.NotSupported:
            return []  # spot doesn't have positions

    # ------------------------------------------------------------------
    # Trading
    # ------------------------------------------------------------------
    async def place_order(self, req: OrderRequest) -> OrderResult:
        params: dict = {}
        if req.reduce_only:
            params['reduceOnly'] = True
        if req.margin_mode == 'isolated' and req.leverage:
            params['leverage'] = req.leverage

        raw = await self._call(
            self._exchange.create_order(
                symbol=req.symbol.exchange_symbol,
                type=req.order_type,
                side=req.side,
                amount=float(req.quantity),
                price=float(req.price) if req.price else None,
                params=params,
            )
        )
        return self._normalize_order(raw, req.client_order_id)

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        try:
            await self._call(self._exchange.cancel_order(order_id, symbol))
            return True
        except Exception as e:
            logger.warning('Cancel order failed: %s', e)
            return False

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> list[str]:
        try:
            orders = await self._call(self._exchange.cancel_all_orders(symbol))
            return [o['id'] for o in (orders or [])]
        except Exception as e:
            logger.error('cancel_all_orders failed: %s', e)
            return []

    async def get_order_status(self, symbol: str, order_id: str) -> OrderResult:
        raw = await self._call(self._exchange.fetch_order(order_id, symbol))
        return self._normalize_order(raw)

    # ------------------------------------------------------------------
    # Market info
    # ------------------------------------------------------------------
    async def get_instrument_info(self, symbol: str) -> dict:
        market = self._exchange.market(symbol)
        return {
            'symbol': symbol,
            'tick_size': Decimal(str(market.get('precision', {}).get('price', '0.01'))),
            'lot_size': Decimal(str(market.get('precision', {}).get('amount', '0.001'))),
            'min_notional': Decimal(str(market.get('limits', {}).get('cost', {}).get('min', '5'))),
            'max_leverage': market.get('limits', {}).get('leverage', {}).get('max', 1),
        }

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 500,
    ) -> list[list]:
        return await self._call(
            self._exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        )

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    async def subscribe_trades(self, symbols: list[str]) -> AsyncIterator[dict]:
        while True:
            for symbol in symbols:
                trades = await self._exchange.watch_trades(symbol)
                for t in trades:
                    yield {
                        'symbol': symbol,
                        'price': Decimal(str(t['price'])),
                        'quantity': Decimal(str(t['amount'])),
                        'side': t['side'],
                        'timestamp_ms': t['timestamp'],
                    }

    async def subscribe_orderbook(self, symbols: list[str]) -> AsyncIterator[dict]:
        while True:
            for symbol in symbols:
                ob = await self._exchange.watch_order_book(symbol)
                yield {'symbol': symbol, 'bids': ob['bids'][:10], 'asks': ob['asks'][:10]}

    async def subscribe_klines(
        self, symbols: list[str], timeframe: str
    ) -> AsyncIterator[dict]:
        while True:
            for symbol in symbols:
                kline = await self._exchange.watch_ohlcv(symbol, timeframe)
                if kline:
                    yield {'symbol': symbol, 'timeframe': timeframe, 'candle': kline[-1]}

    async def subscribe_user_data(self) -> AsyncIterator[dict]:
        while True:
            order = await self._exchange.watch_orders()
            if order:
                yield {'type': 'order_update', 'data': order}

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------
    async def reconcile_positions(self) -> list[dict]:
        return await self.get_positions()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalize_order(self, raw: dict, client_order_id: str = '') -> OrderResult:
        return OrderResult(
            exchange_order_id=str(raw.get('id', '')),
            client_order_id=client_order_id or raw.get('clientOrderId', ''),
            status=self._map_status(raw.get('status', '')),
            filled_qty=Decimal(str(raw.get('filled') or 0)),
            avg_fill_price=Decimal(str(raw.get('average') or raw.get('price') or 0)),
            fees=Decimal(str((raw.get('fee') or {}).get('cost') or 0)),
            fee_currency=str((raw.get('fee') or {}).get('currency', 'USDT')),
            timestamp_ms=int(raw.get('timestamp') or 0),
            raw_response=raw,
        )

    @staticmethod
    def _map_status(status: str) -> str:
        mapping = {
            'open': 'open',
            'closed': 'filled',
            'canceled': 'cancelled',
            'rejected': 'rejected',
            'expired': 'cancelled',
            'partially_filled': 'partially_filled',
        }
        return mapping.get(status, status)
