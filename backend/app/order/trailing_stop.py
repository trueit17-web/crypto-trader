"""
Trailing Stop Engine
Автоматический сдвиг стоп-лосса за ценой.
Поддерживает: ATR-based, процентный, тиковый режимы.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional

log = logging.getLogger(__name__)


class TrailMode(str, Enum):
    PERCENT = "percent"       # % от текущей цены
    ATR = "atr"               # N * ATR(14)
    FIXED = "fixed"           # фиксированное расстояние в $


@dataclass
class TrailingStopConfig:
    mode: TrailMode = TrailMode.PERCENT
    value: float = 1.5          # % или ATR-множитель или $
    activation_pnl_pct: float = 0.5  # активируется после +0.5% прибыли
    min_move: float = 0.05      # не двигать SL если сдвиг < 0.05%


@dataclass
class TrailingStopState:
    position_id: str
    symbol: str
    side: str                   # "long" | "short"
    entry_price: Decimal
    current_sl: Decimal
    best_price: Decimal         # максимум/минимум с момента входа
    activated: bool = False
    config: TrailingStopConfig = field(default_factory=TrailingStopConfig)


class TrailingStopEngine:
    """Отслеживает позиции и двигает SL вслед за ценой."""

    def __init__(self):
        self._states: Dict[str, TrailingStopState] = {}
        self._atr_cache: Dict[str, float] = {}  # symbol -> last ATR

    def register(self, position_id: str, symbol: str, side: str,
                 entry_price: float, initial_sl: float,
                 config: Optional[TrailingStopConfig] = None) -> TrailingStopState:
        """Зарегистрировать новую позицию для трейлинга."""
        state = TrailingStopState(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=Decimal(str(entry_price)),
            current_sl=Decimal(str(initial_sl)),
            best_price=Decimal(str(entry_price)),
            config=config or TrailingStopConfig(),
        )
        self._states[position_id] = state
        log.info("TrailingStop registered pos=%s %s %s entry=%.4f sl=%.4f",
                 position_id, side, symbol, entry_price, initial_sl)
        return state

    def unregister(self, position_id: str) -> None:
        self._states.pop(position_id, None)

    def update_atr(self, symbol: str, atr: float) -> None:
        self._atr_cache[symbol] = atr

    def on_price(self, position_id: str, current_price: float) -> Optional[Decimal]:
        """
        Обновить состояние при новой цене.
        Возвращает новый SL если нужно переставить, иначе None.
        """
        state = self._states.get(position_id)
        if not state:
            return None

        price = Decimal(str(current_price))
        cfg = state.config
        entry = state.entry_price

        # Проверяем активацию
        if not state.activated:
            if state.side == "long":
                pnl_pct = float((price - entry) / entry * 100)
            else:
                pnl_pct = float((entry - price) / entry * 100)

            if pnl_pct < cfg.activation_pnl_pct:
                return None
            state.activated = True
            log.info("TrailingStop ACTIVATED pos=%s price=%.4f pnl=%.2f%%",
                     position_id, current_price, pnl_pct)

        # Обновляем best_price
        if state.side == "long" and price > state.best_price:
            state.best_price = price
        elif state.side == "short" and price < state.best_price:
            state.best_price = price
        else:
            return None  # цена не улучшилась — SL не двигаем

        # Вычисляем новый SL
        new_sl = self._compute_sl(state)

        # Проверяем минимальный сдвиг
        move_pct = abs(float(new_sl - state.current_sl) / float(state.current_sl) * 100)
        if move_pct < cfg.min_move:
            return None

        # Не позволяем SL двигаться против позиции
        if state.side == "long" and new_sl <= state.current_sl:
            return None
        if state.side == "short" and new_sl >= state.current_sl:
            return None

        old_sl = state.current_sl
        state.current_sl = new_sl
        log.info("TrailingStop MOVED pos=%s %s -> %s (price=%.4f)",
                 position_id, float(old_sl), float(new_sl), current_price)
        return new_sl

    def _compute_sl(self, state: TrailingStopState) -> Decimal:
        cfg = state.config
        best = state.best_price

        if cfg.mode == TrailMode.PERCENT:
            offset = best * Decimal(str(cfg.value / 100))
        elif cfg.mode == TrailMode.ATR:
            atr = self._atr_cache.get(state.symbol, 0)
            offset = Decimal(str(atr * cfg.value))
        else:  # FIXED
            offset = Decimal(str(cfg.value))

        if state.side == "long":
            return best - offset
        else:
            return best + offset

    def get_all_states(self) -> Dict[str, TrailingStopState]:
        return dict(self._states)


# Глобальный синглтон
trailing_engine = TrailingStopEngine()
