"""
Pattern Analyzer — анализ паттернов в сигналах.
Выявляет когда и при каких условиях сигналы лучше работают.
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class PatternAnalyzer:
    """
    Анализирует трейды из OutcomeTracker и ищет паттерны:
    - по часу суток (UTC)
    - по дню недели
    - по символу
    - по направлению (long/short)
    - по режиму рынка
    """

    def analyze(self, trades: List[dict]) -> dict:
        """Полный анализ по всем измерениям."""
        closed = [t for t in trades if t.get("outcome") not in ("pending", None)]
        if not closed:
            return {}

        return {
            "by_hour": self._by_dimension(closed, self._get_hour),
            "by_weekday": self._by_dimension(closed, self._get_weekday),
            "by_symbol": self._by_dimension(closed, lambda t: t.get("symbol", "?")),
            "by_direction": self._by_dimension(closed, lambda t: t.get("direction", "?")),
            "by_market_regime": self._by_dimension(closed, lambda t: t.get("market_regime") or "unknown"),
            "best_hours": self._top_n(self._by_dimension(closed, self._get_hour), 3),
            "best_weekdays": self._top_n(self._by_dimension(closed, self._get_weekday), 3),
            "best_symbols": self._top_n(self._by_dimension(closed, lambda t: t.get("symbol", "?")), 5),
        }

    def _by_dimension(self, trades: List[dict],
                       key_fn) -> List[dict]:
        groups: Dict[str, list] = defaultdict(list)
        for t in trades:
            k = key_fn(t)
            groups[k].append(t)

        result = []
        for k, group in sorted(groups.items()):
            wins = sum(1 for t in group if t.get("outcome") in ("win", "partial"))
            pnls = [t["pnl_pct"] for t in group if t.get("pnl_pct") is not None]
            result.append({
                "key": k,
                "trades": len(group),
                "win_rate": round(wins / len(group) * 100, 1),
                "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
                "total_pnl": round(sum(pnls), 2) if pnls else 0,
            })
        return result

    def _top_n(self, items: List[dict], n: int,
               sort_by: str = "win_rate") -> List[dict]:
        return sorted(items, key=lambda x: x.get(sort_by, 0),
                      reverse=True)[:n]

    @staticmethod
    def _get_hour(trade: dict) -> str:
        ts = trade.get("entry_ts", "")
        try:
            from datetime import datetime
            hour = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
            return f"{hour:02d}:00"
        except Exception:
            return "??"

    @staticmethod
    def _get_weekday(trade: dict) -> str:
        ts = trade.get("entry_ts", "")
        try:
            from datetime import datetime
            day = datetime.fromisoformat(ts.replace("Z", "+00:00")).weekday()
            return DAY_NAMES[day]
        except Exception:
            return "?"


pattern_analyzer = PatternAnalyzer()
