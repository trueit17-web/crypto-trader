"""
Auto-Hedge Engine — автоматическое хеджирование.
Открывает обратную позицию при просадке больше порога.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class HedgeStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"       # хедж открыт
    CLOSED = "closed"       # хедж закрыт


@dataclass
class AutoHedgeConfig:
    trigger_drawdown_pct: float = 3.0     # активируется при -3% от входа
    hedge_size_pct: float = 100.0         # 100% обратной позиции
    close_on_recovery_pct: float = 1.5    # закрыть хедж при восстановлении +1.5%
    max_hedge_duration_hours: int = 24    # авто-закрытие через N часов
    allow_re_hedge: bool = False          # повторное хеджирование


@dataclass
class HedgeState:
    position_id: str
    symbol: str
    original_side: str        # "long" | "short"
    entry_price: Decimal
    original_size: Decimal
    status: HedgeStatus = HedgeStatus.INACTIVE
    hedge_order_id: Optional[str] = None
    hedge_entry_price: Optional[Decimal] = None
    hedge_size: Optional[Decimal] = None
    hedges_opened: int = 0
    config: AutoHedgeConfig = None

    def __post_init__(self):
        if self.config is None:
            self.config = AutoHedgeConfig()


class AutoHedgeEngine:
    """Отслеживает P&L и сигнализирует открытие/закрытие хедж."""

    def __init__(self):
        self._states: dict[str, HedgeState] = {}

    def register(self, position_id: str, symbol: str, side: str,
                 entry_price: float, size: float,
                 config: Optional[AutoHedgeConfig] = None) -> HedgeState:
        state = HedgeState(
            position_id=position_id, symbol=symbol,
            original_side=side,
            entry_price=Decimal(str(entry_price)),
            original_size=Decimal(str(size)),
            config=config or AutoHedgeConfig(),
        )
        self._states[position_id] = state
        return state

    def unregister(self, position_id: str) -> None:
        self._states.pop(position_id, None)

    def on_price(self, position_id: str, current_price: float) -> Optional[dict]:
        """
        Возвращает словарь действия: {action: open|close, side, size, reason}
        """
        state = self._states.get(position_id)
        if not state:
            return None

        price = Decimal(str(current_price))
        cfg = state.config
        entry = state.entry_price

        if state.original_side == "long":
            pnl_pct = float((price - entry) / entry * 100)
        else:
            pnl_pct = float((entry - price) / entry * 100)

        # --- Сигнал: открыть хедж ---
        if state.status == HedgeStatus.INACTIVE:
            if pnl_pct <= -cfg.trigger_drawdown_pct:
                if not cfg.allow_re_hedge and state.hedges_opened > 0:
                    return None

                hedge_side = "short" if state.original_side == "long" else "long"
                hedge_size = state.original_size * Decimal(str(cfg.hedge_size_pct / 100))

                state.status = HedgeStatus.ACTIVE
                state.hedge_entry_price = price
                state.hedge_size = hedge_size
                state.hedges_opened += 1

                log.warning("AutoHedge OPEN pos=%s drawdown=%.2f%% hedge=%s size=%.4f",
                            position_id, abs(pnl_pct), hedge_side, float(hedge_size))
                return {
                    "action": "open_hedge",
                    "side": hedge_side,
                    "size": float(hedge_size),
                    "price": float(price),
                    "reason": f"drawdown_{abs(pnl_pct):.2f}pct",
                }

        # --- Сигнал: закрыть хедж ---
        elif state.status == HedgeStatus.ACTIVE and state.hedge_entry_price:
            h_entry = state.hedge_entry_price
            hedge_side = "short" if state.original_side == "long" else "long"

            if hedge_side == "short":
                hedge_pnl = float((h_entry - price) / h_entry * 100)
            else:
                hedge_pnl = float((price - h_entry) / h_entry * 100)

            if hedge_pnl >= cfg.close_on_recovery_pct:
                state.status = HedgeStatus.CLOSED
                log.info("AutoHedge CLOSE pos=%s hedge_pnl=+%.2f%%",
                         position_id, hedge_pnl)
                return {
                    "action": "close_hedge",
                    "side": hedge_side,
                    "size": float(state.hedge_size),
                    "price": float(price),
                    "reason": f"recovery_{hedge_pnl:.2f}pct",
                }

        return None


auto_hedge_engine = AutoHedgeEngine()
