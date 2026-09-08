"""
Partial Close — частичное закрытие позиции.
Позволяет фиксировать прибыль по частям (TP1 50%, TP2 30%, TP3 20%).
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class PartialCloseLevel:
    """Один уровень частичного закрытия."""
    price: float            # цена тейк-профита
    close_pct: float        # % позиции для закрытия (0-100)
    executed: bool = False
    order_id: Optional[str] = None


@dataclass
class PartialCloseConfig:
    levels: List[PartialCloseLevel]
    move_sl_to_entry: bool = True   # после TP1 двигать SL в безубыток
    move_sl_to_tp1: bool = False    # после TP2 двигать SL на уровень TP1

    def __post_init__(self):
        total = sum(l.close_pct for l in self.levels)
        if abs(total - 100.0) > 0.01 and total > 100.0:
            raise ValueError(f"Сумма close_pct уровней = {total}, не должна превышать 100%")


class PartialCloseManager:
    """Управляет частичными закрытиями для каждой позиции."""

    def __init__(self):
        self._configs: dict[str, PartialCloseConfig] = {}
        self._original_size: dict[str, Decimal] = {}
        self._remaining_size: dict[str, Decimal] = {}

    def register(self, position_id: str, size: float,
                 config: PartialCloseConfig) -> None:
        """Зарегистрировать позицию с планом частичных закрытий."""
        self._configs[position_id] = config
        self._original_size[position_id] = Decimal(str(size))
        self._remaining_size[position_id] = Decimal(str(size))
        log.info("PartialClose registered pos=%s size=%.4f levels=%d",
                 position_id, size, len(config.levels))

    def unregister(self, position_id: str) -> None:
        for d in (self._configs, self._original_size, self._remaining_size):
            d.pop(position_id, None)

    def on_price(self, position_id: str, current_price: float,
                 side: str) -> List[dict]:
        """
        Проверить нужно ли частично закрыться.
        Возвращает список действий [{level_idx, close_size, reason}].
        """
        cfg = self._configs.get(position_id)
        if not cfg:
            return []

        price = Decimal(str(current_price))
        remaining = self._remaining_size[position_id]
        original = self._original_size[position_id]
        actions = []

        for idx, level in enumerate(cfg.levels):
            if level.executed:
                continue

            tp = Decimal(str(level.price))
            hit = (side == "long" and price >= tp) or (side == "short" and price <= tp)

            if hit:
                close_size = original * Decimal(str(level.close_pct / 100))
                close_size = min(close_size, remaining)  # не больше остатка

                level.executed = True
                remaining -= close_size
                self._remaining_size[position_id] = remaining

                actions.append({
                    "level_idx": idx,
                    "close_size": float(close_size),
                    "close_pct": level.close_pct,
                    "tp_price": level.price,
                    "remaining_size": float(remaining),
                    "move_sl_to_entry": idx == 0 and cfg.move_sl_to_entry,
                    "move_sl_to_tp1": idx == 1 and cfg.move_sl_to_tp1,
                })
                log.info("PartialClose TRIGGERED pos=%s level=%d close_size=%.4f remaining=%.4f",
                         position_id, idx, float(close_size), float(remaining))

        return actions

    def get_remaining(self, position_id: str) -> Optional[float]:
        r = self._remaining_size.get(position_id)
        return float(r) if r is not None else None

    @staticmethod
    def default_config(entry: float, tp1_pct: float = 1.5,
                       tp2_pct: float = 3.0, tp3_pct: float = 5.0,
                       side: str = "long") -> PartialCloseConfig:
        """Стандартная 3-уровневая конфигурация."""
        mult = 1 if side == "long" else -1
        e = Decimal(str(entry))
        return PartialCloseConfig(levels=[
            PartialCloseLevel(price=float(e * Decimal(str(1 + mult * tp1_pct / 100))),
                              close_pct=50),
            PartialCloseLevel(price=float(e * Decimal(str(1 + mult * tp2_pct / 100))),
                              close_pct=30),
            PartialCloseLevel(price=float(e * Decimal(str(1 + mult * tp3_pct / 100))),
                              close_pct=20),
        ], move_sl_to_entry=True, move_sl_to_tp1=True)


# Глобальный синглтон
partial_close_manager = PartialCloseManager()
