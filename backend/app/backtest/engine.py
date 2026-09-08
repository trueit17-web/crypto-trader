"""Backtesting engine with strict look-ahead bias protection (Section L)."""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
import logging

from app.strategy.base import BaseStrategy, StrategySignal

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    symbol: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    entry_ts: int
    exit_ts: int
    pnl: Decimal
    pnl_pct: float
    fees: Decimal
    exit_reason: str  # tp | sl | trailing | end


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: list[tuple[int, Decimal]]  # (timestamp_ms, equity)
    initial_capital: Decimal
    final_equity: Decimal
    metrics: dict


class SimulatedPortfolio:
    def __init__(self, initial_capital: Decimal, fee_rate: float = 0.0005):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.equity_curve: list[tuple[int, Decimal]] = []
        self._open: Optional[dict] = None  # one position at a time
        self.closed_trades: list[Trade] = []

    def open_position(self, signal: StrategySignal, fill_price: Decimal,
                      timestamp_ms: int, fee: Decimal) -> Optional[Trade]:
        if self._open:
            return None  # already in a trade
        notional = self.capital * Decimal(str(signal.size_fraction))
        quantity = notional / fill_price
        self.capital -= fee
        self._open = {
            'symbol': signal.symbol,
            'direction': signal.direction,
            'entry_price': fill_price,
            'quantity': quantity,
            'stop_loss': Decimal(str(signal.stop_loss)),
            'take_profits': [Decimal(str(tp)) for tp in signal.take_profits],
            'entry_ts': timestamp_ms,
            'fee': fee,
        }
        return None

    def check_sl_tp(self, candle: dict) -> list[Trade]:
        if not self._open:
            return []
        high = Decimal(str(candle['high']))
        low = Decimal(str(candle['low']))
        pos = self._open
        direction = pos['direction']

        exit_price = None
        exit_reason = None

        if direction == 'long':
            if low <= pos['stop_loss']:
                exit_price = pos['stop_loss']
                exit_reason = 'sl'
            elif pos['take_profits'] and high >= pos['take_profits'][0]:
                exit_price = pos['take_profits'][0]
                exit_reason = 'tp'
        else:  # short
            if high >= pos['stop_loss']:
                exit_price = pos['stop_loss']
                exit_reason = 'sl'
            elif pos['take_profits'] and low <= pos['take_profits'][0]:
                exit_price = pos['take_profits'][0]
                exit_reason = 'tp'

        if exit_price:
            return [self._close_position(exit_price, candle['timestamp'], exit_reason)]
        return []

    def _close_position(self, exit_price: Decimal, ts: int, reason: str) -> Trade:
        pos = self._open
        gross_pnl = (exit_price - pos['entry_price']) * pos['quantity']
        if pos['direction'] == 'short':
            gross_pnl = -gross_pnl
        exit_fee = exit_price * pos['quantity'] * Decimal(str(self.fee_rate))
        net_pnl = gross_pnl - exit_fee - pos['fee']
        self.capital += net_pnl + pos['quantity'] * pos['entry_price']
        trade = Trade(
            symbol=pos['symbol'],
            direction=pos['direction'],
            entry_price=pos['entry_price'],
            exit_price=exit_price,
            quantity=pos['quantity'],
            entry_ts=pos['entry_ts'],
            exit_ts=ts,
            pnl=net_pnl,
            pnl_pct=float(net_pnl / (pos['entry_price'] * pos['quantity'])),
            fees=exit_fee + pos['fee'],
            exit_reason=reason,
        )
        self.closed_trades.append(trade)
        self._open = None
        return trade

    def update_marks(self, current_price: Decimal, timestamp_ms: int) -> None:
        equity = self.capital
        if self._open:
            pos = self._open
            unreal = (current_price - pos['entry_price']) * pos['quantity']
            if pos['direction'] == 'short':
                unreal = -unreal
            equity += unreal
        self.equity_curve.append((timestamp_ms, equity))


class BacktestEngine:
    """Runs strategy against historical candles with NO look-ahead."""

    WARMUP_PERIODS = 50  # candles consumed for indicator warmup

    def __init__(self, strategy: 'BaseStrategy', config: Optional[dict] = None):
        self.strategy = strategy
        self.cfg = {
            'fee_rate': 0.0005,      # 0.05% per side
            'slippage_bps': 5,       # 0.05% slippage
            'initial_capital': 10000,
            **(config or {}),
        }

    async def run(
        self,
        symbol: str,
        candles: list[dict],   # [{timestamp, open, high, low, close, volume}]
    ) -> BacktestResult:
        initial = Decimal(str(self.cfg['initial_capital']))
        portfolio = SimulatedPortfolio(initial, fee_rate=self.cfg['fee_rate'])
        trades: list[Trade] = []

        for i in range(self.WARMUP_PERIODS, len(candles) - 1):
            historical = candles[:i + 1]  # STRICT: only past data
            current = candles[i]
            next_c = candles[i + 1]  # execution candle (open of next)

            # Close checks first
            closed = portfolio.check_sl_tp(current)
            trades.extend(closed)

            # Strategy signal
            signal = await self.strategy.on_bar(symbol, '1h', current)

            if signal and not portfolio._open:
                fill_price = self._simulate_fill(
                    signal, next_c, self.cfg['slippage_bps']
                )
                fee = fill_price * Decimal(str(signal.size_fraction)) * Decimal(str(self.cfg['fee_rate']))
                portfolio.open_position(signal, fill_price, next_c['timestamp'], fee)

            portfolio.update_marks(Decimal(str(current['close'])), current['timestamp'])

        # Force-close any open position at end
        if portfolio._open and candles:
            last = candles[-1]
            trade = portfolio._close_position(
                Decimal(str(last['close'])), last['timestamp'], 'end'
            )
            trades.append(trade)

        metrics = self._calculate_metrics(trades, portfolio, initial)
        return BacktestResult(
            trades=trades,
            equity_curve=portfolio.equity_curve,
            initial_capital=initial,
            final_equity=portfolio.capital,
            metrics=metrics,
        )

    def _simulate_fill(
        self, signal: 'StrategySignal', next_candle: dict, slippage_bps: int
    ) -> Decimal:
        slippage = Decimal(str(signal.entry_price or next_candle['open'])) * Decimal(slippage_bps) / 10000
        base = Decimal(str(signal.entry_price or next_candle['open']))
        if signal.direction == 'long':
            return min(base + slippage, Decimal(str(next_candle['high'])))
        else:
            return max(base - slippage, Decimal(str(next_candle['low'])))

    @staticmethod
    def _calculate_metrics(trades: list[Trade], portfolio: SimulatedPortfolio,
                           initial: Decimal) -> dict:
        if not trades:
            return {'error': 'no trades'}
        pnls = [float(t.pnl) for t in trades]
        winners = [p for p in pnls if p > 0]
        losers  = [p for p in pnls if p < 0]
        win_rate = len(winners) / len(trades) if trades else 0
        gross_profit = sum(winners) if winners else 0
        gross_loss   = abs(sum(losers)) if losers else 1
        # Max drawdown from equity curve
        equity_vals = [float(e) for _, e in portfolio.equity_curve]
        peak = equity_vals[0] if equity_vals else float(initial)
        max_dd = 0.0
        for v in equity_vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
        net_return = (float(portfolio.capital) - float(initial)) / float(initial)
        return {
            'total_trades': len(trades),
            'win_rate': round(win_rate, 4),
            'net_return': round(net_return, 4),
            'gross_profit': round(gross_profit, 2),
            'gross_loss': round(gross_loss, 2),
            'profit_factor': round(gross_profit / gross_loss, 2) if gross_loss else 0,
            'max_drawdown': round(max_dd, 4),
            'avg_pnl': round(sum(pnls) / len(pnls), 2) if pnls else 0,
        }
