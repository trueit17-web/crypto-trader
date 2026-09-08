"""
Outcome Tracker — записывает результат каждой сделки для обучения ML.
Naive SQLite в режиме paper/shadow, Postgres в проде.
"""
from __future__ import annotations
import json
import sqlite3
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)
DB_PATH = Path("/data/crypto-trader/data/ml_outcomes.db")


class TradeOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    PARTIAL = "partial"   # частичное закрытие
    TIMEOUT = "timeout"   # закрыто по времени
    PENDING = "pending"   # не закрыто


@dataclass
class TradeRecord:
    signal_id: str
    source: str           # telegram channel, webhook, manual
    symbol: str
    direction: str        # long | short
    entry_price: float
    tp: Optional[float]
    sl: Optional[float]
    leverage: float
    size_usdt: float
    entry_ts: str         # ISO
    exit_price: Optional[float] = None
    exit_ts: Optional[str] = None
    outcome: TradeOutcome = TradeOutcome.PENDING
    pnl_pct: Optional[float] = None
    pnl_usdt: Optional[float] = None
    hold_minutes: Optional[int] = None
    market_regime: Optional[str] = None   # bull/bear/sideways
    features: Optional[dict] = None       # ML features snapshot


class OutcomeTracker:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                signal_id TEXT PRIMARY KEY,
                source TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                tp REAL,
                sl REAL,
                leverage REAL,
                size_usdt REAL,
                entry_ts TEXT,
                exit_price REAL,
                exit_ts TEXT,
                outcome TEXT DEFAULT 'pending',
                pnl_pct REAL,
                pnl_usdt REAL,
                hold_minutes INTEGER,
                market_regime TEXT,
                features TEXT
            )
        """)
        self._conn.commit()

    def record_entry(self, rec: TradeRecord) -> None:
        d = asdict(rec)
        d["features"] = json.dumps(d.get("features") or {})
        cols = list(d.keys())
        placeholders = ",".join(["?"] * len(cols))
        self._conn.execute(
            f"INSERT OR REPLACE INTO trades ({','.join(cols)}) VALUES ({placeholders})",
            [d[c] for c in cols]
        )
        self._conn.commit()
        log.info("OutcomeTracker ENTRY signal=%s %s %s",
                 rec.signal_id, rec.symbol, rec.direction)

    def record_exit(self, signal_id: str, exit_price: float,
                    outcome: TradeOutcome, pnl_pct: float, pnl_usdt: float,
                    hold_minutes: int) -> None:
        self._conn.execute("""
            UPDATE trades SET
                exit_price=?, exit_ts=?, outcome=?,
                pnl_pct=?, pnl_usdt=?, hold_minutes=?
            WHERE signal_id=?
        """, [
            exit_price,
            datetime.now(timezone.utc).isoformat(),
            outcome.value, pnl_pct, pnl_usdt, hold_minutes,
            signal_id
        ])
        self._conn.commit()
        log.info("OutcomeTracker EXIT signal=%s outcome=%s pnl=%.2f%%",
                 signal_id, outcome.value, pnl_pct)

    def get_source_stats(self, source: str, window_days: int = 30) -> dict:
        """Win rate, avg P&L, Sharpe для источника за N дней."""
        rows = self._conn.execute("""
            SELECT outcome, pnl_pct FROM trades
            WHERE source=? AND outcome != 'pending'
              AND entry_ts >= datetime('now', ?)
        """, [source, f"-{window_days} days"]).fetchall()

        if not rows:
            return {"source": source, "trades": 0, "win_rate": None,
                    "avg_pnl": None, "total_pnl": None}

        wins = sum(1 for r in rows if r[0] in ("win", "partial"))
        pnls = [r[1] for r in rows if r[1] is not None]
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0

        return {
            "source": source,
            "trades": len(rows),
            "win_rate": wins / len(rows),
            "avg_pnl": avg_pnl,
            "total_pnl": sum(pnls),
        }

    def get_all_sources(self, window_days: int = 30) -> List[dict]:
        sources = self._conn.execute(
            "SELECT DISTINCT source FROM trades"
        ).fetchall()
        return [self.get_source_stats(s[0], window_days) for s in sources]

    def get_training_data(self, min_trades: int = 50) -> List[dict]:
        """ML данные: только закрытые сделки с features."""
        rows = self._conn.execute("""
            SELECT * FROM trades
            WHERE outcome != 'pending' AND features IS NOT NULL
        """).fetchall()
        cols = [d[0] for d in self._conn.execute(
            "SELECT * FROM trades LIMIT 0").description]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            try:
                d["features"] = json.loads(d["features"] or "{}")
            except Exception:
                d["features"] = {}
            result.append(d)
        return result


outcome_tracker = OutcomeTracker()
