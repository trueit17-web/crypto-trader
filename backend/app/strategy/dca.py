"""
DCA (Dollar-Cost Averaging) Mode — усреднение по сетке.
Открывает дополнительные ордера при движении против позиции.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class DCAStep:
    drop_pct: float        # % просадки от входа
    add_pct: float         # % от первоначального размера
    executed: bool = False
    order_id: Optional[str] = None


@dataclass
class DCAConfig:
    steps: List[DCAStep] = field(default_factory=lambda: [
        DCAStep(drop_pct=1.5, add_pct=100),   # -1.5% → x2
        DCAStep(drop_pct=3.0, add_pct=150),   # -3.0% → x2.5
        DCAStep(drop_pct=5.0, add_pct=200),   # -5.0% → x3
    ])
    max_total_multiplier: float = 5.0   # макс 5x от первоначальной позиции
    use_safety_orders: bool = True      # выставлять лимит-ордера заранее


@dataclass
class DCAState:
    position_id: str
    symbol: str
    side: str
    entry_price: Decimal
    original_size: Decimal
    current_size: Decimal
    average_price: Decimal
    steps_done: int = 0
    config: DCAConfig = field(default_factory=DCAConfig)

    def update_average(self, new_price: Decimal, add_size: Decimal) -> None:
        total_size = self.current_size + add_size
        self.average_price = (
            self.average_price * self.current_size + new_price * add_size
        ) / total_size
        self.current_size = total_size


class DCAEngine:
    """Движок DCA: следит за ценой и добавляет при просадке."""

    def __init__(self):
        self._states: dict[str, DCAState] = {}

    def register(self, position_id: str, symbol: str, side: str,
                 entry_price: float, size: float,
                 config: Optional[DCAConfig] = None) -> DCAState:
        cfg = config or DCAConfig()
        state = DCAState(
            position_id=position_id, symbol=symbol, side=side,
            entry_price=Decimal(str(entry_price)),
            original_size=Decimal(str(size)),
            current_size=Decimal(str(size)),
            average_price=Decimal(str(entry_price)),
            config=cfg,
        )
        self._states[position_id] = state
        log.info("DCA registered pos=%s %s %s entry=%.4f size=%.4f",
                 position_id, side, symbol, entry_price, size)
        return state

    def unregister(self, position_id: str) -> None:
        self._states.pop(position_id, None)

    def on_price(self, position_id: str, current_price: float) -> List[dict]:
        """Возвращает [{add_size, target_price, reason}] при необходимости DCA."""
        state = self._states.get(position_id)
        if not state:
            return []

        price = Decimal(str(current_price))
        entry = state.entry_price
        cfg = state.config

        if state.side == "long":
            drop_pct = float((entry - price) / entry * 100)
        else:
            drop_pct = float((price - entry) / entry * 100)

        max_size = state.original_size * Decimal(str(cfg.max_total_multiplier))
        actions = []

        for step in cfg.steps:
            if step.executed:
                continue
            if drop_pct < step.drop_pct:
                continue
            if state.current_size >= max_size:
                break

            add_size = state.original_size * Decimal(str(step.add_pct / 100))
            add_size = min(add_size, max_size - state.current_size)

            step.executed = True
            state.update_average(price, add_size)
            state.steps_done += 1

            actions.append({
                "add_size": float(add_size),
                "target_price": float(price),
                "drop_pct": step.drop_pct,
                "new_average": float(state.average_price),
                "new_total_size": float(state.current_size),
                "reason": f"dca_step_{state.steps_done}",
            })
            log.info("DCA STEP pos=%s step=%d add=%.4f avg=%.4f drop=%.2f%%",
                     position_id, state.steps_done,
                     float(add_size), float(state.average_price), drop_pct)

        return actions

    def get_state(self, position_id: str) -> Optional[DCAState]:
        return self._states.get(position_id)


dca_engine = DCAEngine()
