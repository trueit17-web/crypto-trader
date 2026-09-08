"""
Pyramiding Strategy — добавление к прибыльной позиции.
Добавляет часть позиции при подтверждении тренда.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class PyramidLevel:
    trigger_pnl_pct: float   # добавить при +X% P&L
    add_pct: float           # % от оригинального размера
    executed: bool = False
    order_id: Optional[str] = None


@dataclass
class PyramidingConfig:
    max_additions: int = 3              # макс добавлений
    max_total_size_pct: float = 300.0   # макс от первоначальной позиции (%)
    require_new_high: bool = True       # добавлять только на новом хаее/лоую
    levels: List[PyramidLevel] = field(default_factory=lambda: [
        PyramidLevel(trigger_pnl_pct=1.5, add_pct=50),   # +1.5% → +50%
        PyramidLevel(trigger_pnl_pct=3.0, add_pct=30),   # +3.0% → +30%
        PyramidLevel(trigger_pnl_pct=5.0, add_pct=20),   # +5.0% → +20%
    ])


@dataclass
class PyramidState:
    position_id: str
    symbol: str
    side: str
    entry_price: Decimal
    original_size: Decimal
    current_size: Decimal
    high_water_mark: Decimal     # максимум/минимум прице (long/short)
    additions_count: int = 0
    config: PyramidingConfig = field(default_factory=PyramidingConfig)


class PyramidingEngine:
    """Отслеживает P&L и генерирует сигналы на добавление."""

    def __init__(self):
        self._states: dict[str, PyramidState] = {}

    def register(self, position_id: str, symbol: str, side: str,
                 entry_price: float, size: float,
                 config: Optional[PyramidingConfig] = None) -> PyramidState:
        cfg = config or PyramidingConfig()
        state = PyramidState(
            position_id=position_id,
            symbol=symbol,
            side=side,
            entry_price=Decimal(str(entry_price)),
            original_size=Decimal(str(size)),
            current_size=Decimal(str(size)),
            high_water_mark=Decimal(str(entry_price)),
            config=cfg,
        )
        self._states[position_id] = state
        return state

    def unregister(self, position_id: str) -> None:
        self._states.pop(position_id, None)

    def on_price(self, position_id: str, current_price: float) -> List[dict]:
        """
        Возвращает список сигналов добавления [{add_size, reason}].
        """
        state = self._states.get(position_id)
        if not state:
            return []

        price = Decimal(str(current_price))
        cfg = state.config

        if state.additions_count >= cfg.max_additions:
            return []

        # Проверяем new high/low
        if cfg.require_new_high:
            if state.side == "long" and price <= state.high_water_mark:
                return []
            if state.side == "short" and price >= state.high_water_mark:
                return []

        # Обновляем high water mark
        if state.side == "long":
            state.high_water_mark = max(state.high_water_mark, price)
        else:
            state.high_water_mark = min(state.high_water_mark, price)

        entry = state.entry_price
        if state.side == "long":
            pnl_pct = float((price - entry) / entry * 100)
        else:
            pnl_pct = float((entry - price) / entry * 100)

        actions = []
        for level in cfg.levels:
            if level.executed:
                continue
            if pnl_pct < level.trigger_pnl_pct:
                continue

            # Проверка лимита общего размера
            max_size = state.original_size * Decimal(str(cfg.max_total_size_pct / 100))
            if state.current_size >= max_size:
                break

            add_size = state.original_size * Decimal(str(level.add_pct / 100))
            add_size = min(add_size, max_size - state.current_size)

            level.executed = True
            state.additions_count += 1
            state.current_size += add_size

            actions.append({
                "add_size": float(add_size),
                "trigger_pnl_pct": level.trigger_pnl_pct,
                "add_pct": level.add_pct,
                "reason": f"pyramid_L{state.additions_count}",
                "price": float(price),
            })
            log.info("Pyramiding ADD pos=%s size=+%.4f total=%.4f pnl=%.2f%%",
                     position_id, float(add_size),
                     float(state.current_size), pnl_pct)

        return actions


pyramiding_engine = PyramidingEngine()
