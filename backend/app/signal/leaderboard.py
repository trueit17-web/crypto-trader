"""
Signal Source Leaderboard — рейтинг источников сигналов.
Подсчитывает P&L, Win Rate, Sharpe, Profit Factor, Max DD.
"""
from __future__ import annotations
import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class SourceStats:
    source: str
    trades_total: int = 0
    trades_win: int = 0
    trades_loss: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0   # абсолютное значение
    pnl_series: List[float] = field(default_factory=list)
    status: str = "active"    # active | reduced | shadow | suspended
    win_rate_7d: Optional[float] = None
    win_rate_30d: Optional[float] = None

    # --- вычисляемые метрики ---
    @property
    def win_rate(self) -> Optional[float]:
        if self.trades_total == 0:
            return None
        return self.trades_win / self.trades_total

    @property
    def profit_factor(self) -> Optional[float]:
        if self.gross_loss == 0:
            return None
        return self.gross_profit / self.gross_loss

    @property
    def net_pnl(self) -> float:
        return self.gross_profit - self.gross_loss

    @property
    def avg_pnl(self) -> Optional[float]:
        if not self.pnl_series:
            return None
        return sum(self.pnl_series) / len(self.pnl_series)

    @property
    def sharpe(self) -> Optional[float]:
        if len(self.pnl_series) < 5:
            return None
        n = len(self.pnl_series)
        mean = sum(self.pnl_series) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in self.pnl_series) / n)
        return (mean / std * math.sqrt(252)) if std > 0 else None

    @property
    def max_drawdown(self) -> float:
        """Max drawdown по series P&L."""
        if not self.pnl_series:
            return 0.0
        peak = cum = 0.0
        max_dd = 0.0
        for pnl in self.pnl_series:
            cum += pnl
            if cum > peak:
                peak = cum
            dd = peak - cum
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "trades": self.trades_total,
            "win_rate": round(self.win_rate * 100, 1) if self.win_rate else None,
            "win_rate_7d": round(self.win_rate_7d * 100, 1) if self.win_rate_7d else None,
            "win_rate_30d": round(self.win_rate_30d * 100, 1) if self.win_rate_30d else None,
            "net_pnl": round(self.net_pnl, 2),
            "avg_pnl": round(self.avg_pnl, 2) if self.avg_pnl else None,
            "profit_factor": round(self.profit_factor, 2) if self.profit_factor else None,
            "sharpe": round(self.sharpe, 2) if self.sharpe else None,
            "max_drawdown": round(self.max_drawdown, 2),
            "status": self.status,
        }


class Leaderboard:
    """Кэширует и обновляет статистику источников из OutcomeTracker."""

    def __init__(self):
        self._stats: dict[str, SourceStats] = {}

    def rebuild(self, rows: List[dict]) -> None:
        """Перестроить из сырых данных outcome_tracker."""
        stats: dict[str, SourceStats] = {}
        for r in rows:
            if r.get("outcome") == "pending":
                continue
            src = r["source"]
            if src not in stats:
                stats[src] = SourceStats(source=src)
            s = stats[src]
            s.trades_total += 1
            pnl = r.get("pnl_pct") or 0.0
            s.pnl_series.append(pnl)
            if r["outcome"] in ("win", "partial"):
                s.trades_win += 1
                s.gross_profit += max(pnl, 0)
            else:
                s.trades_loss += 1
                s.gross_loss += abs(min(pnl, 0))
        self._stats = stats
        log.info("Leaderboard rebuilt: %d sources", len(stats))

    def update_one(self, source: str, outcome: str, pnl_pct: float) -> None:
        """Live-обновление при закрытии сделки."""
        if source not in self._stats:
            self._stats[source] = SourceStats(source=source)
        s = self._stats[source]
        s.trades_total += 1
        s.pnl_series.append(pnl_pct)
        if outcome in ("win", "partial"):
            s.trades_win += 1
            s.gross_profit += max(pnl_pct, 0)
        else:
            s.trades_loss += 1
            s.gross_loss += abs(min(pnl_pct, 0))

    def set_status(self, source: str, status: str) -> None:
        if source in self._stats:
            self._stats[source].status = status

    def get_ranked(self, sort_by: str = "net_pnl") -> List[dict]:
        items = [s.to_dict() for s in self._stats.values()]
        items.sort(key=lambda x: x.get(sort_by) or 0, reverse=True)
        for i, item in enumerate(items):
            item["rank"] = i + 1
        return items

    def get_source(self, source: str) -> Optional[SourceStats]:
        return self._stats.get(source)


leaderboard = Leaderboard()
