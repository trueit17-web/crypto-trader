"""
Champion-Challenger ML — авторегуляция сигнальных источников.
Чемпион — лучшая модель, чалленджер — новая модель на проверке.
"""
from __future__ import annotations
import json
import logging
import pickle
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)
MODELS_DIR = Path("/data/crypto-trader/data/ml_models")
DB_PATH = Path("/data/crypto-trader/data/ml_outcomes.db")

try:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import train_test_split
    import numpy as np
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    log.warning("sklearn not installed — ML disabled. pip install scikit-learn")


@dataclass
class ModelRecord:
    source: str
    version: int
    trained_at: str
    n_samples: int
    auc: float
    win_rate: float
    is_champion: bool
    model_path: str


class ChampionChallenger:
    """
    Для каждого источника хранит champion (прод модель) и challenger (кандидат).
    Каждую неделю переобучает на новых данных.
    Если challenger лучше champion — заменяет.
    """

    MIN_SAMPLES = 200
    AUC_PROMOTE_THRESHOLD = 0.02  # challenger должен быть лучше на 2%

    def __init__(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        self._champions: Dict[str, object] = {}     # source -> sklearn model
        self._challengers: Dict[str, object] = {}
        self._records: Dict[str, ModelRecord] = {}
        self._load_champions()

    # --- Предсказание для одного сигнала ---
    def predict_win_prob(self, source: str, features: dict) -> Optional[float]:
        if not ML_AVAILABLE:
            return None
        model = self._champions.get(source)
        if model is None:
            return None
        try:
            X = self._features_to_vector([features])
            prob = model.predict_proba(X)[0][1]
            return float(prob)
        except Exception as e:
            log.warning("predict_win_prob failed source=%s err=%s", source, e)
            return None

    # --- Обучение ---
    def retrain(self, source: str, training_data: List[dict]) -> Optional[ModelRecord]:
        if not ML_AVAILABLE:
            log.warning("Cannot retrain: sklearn not available")
            return None

        closed = [r for r in training_data
                  if r["source"] == source and r["outcome"] != "pending"]
        if len(closed) < self.MIN_SAMPLES:
            log.info("Not enough data for %s: %d < %d",
                     source, len(closed), self.MIN_SAMPLES)
            return None

        X = self._features_to_vector(
            [json.loads(r["features"]) if isinstance(r["features"], str)
             else (r["features"] or {}) for r in closed])
        y = np.array([1 if r["outcome"] in ("win", "partial") else 0
                      for r in closed])

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42)

        challenger = GradientBoostingClassifier(
            n_estimators=100, max_depth=3, random_state=42)
        challenger.fit(X_train, y_train)
        auc = roc_auc_score(y_test, challenger.predict_proba(X_test)[:, 1])

        current = self._records.get(source)
        version = (current.version + 1) if current else 1

        # Сравнение с champion
        champion_auc = current.auc if current else 0.0
        should_promote = auc >= champion_auc + self.AUC_PROMOTE_THRESHOLD

        model_path = str(MODELS_DIR / f"{source}_v{version}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(challenger, f)

        win_rate = float(y.mean())
        rec = ModelRecord(
            source=source, version=version,
            trained_at=datetime.now(timezone.utc).isoformat(),
            n_samples=len(closed), auc=auc, win_rate=win_rate,
            is_champion=should_promote, model_path=model_path)

        if should_promote:
            self._champions[source] = challenger
            log.info("CC PROMOTE challenger->champion source=%s auc=%.3f->%.3f",
                     source, champion_auc, auc)
        else:
            self._challengers[source] = challenger
            log.info("CC challenger kept source=%s auc=%.3f (champion=%.3f)",
                     source, auc, champion_auc)

        self._records[source] = rec
        self._save_record(rec)
        return rec

    # --- Автоматическая блокировка слабых источников ---
    def get_source_action(self, source: str,
                          stats: dict) -> Optional[str]:
        """
        Возвращает действие: None | 'reduce_size' | 'shadow' | 'suspend'
        На основе win_rate и количества сделок.
        """
        trades = stats.get("trades", 0)
        win_rate = stats.get("win_rate")
        avg_pnl = stats.get("avg_pnl", 0)

        if trades < 20:
            return None  # недостаточно данных
        if win_rate is None:
            return None

        if win_rate < 0.25 and trades >= 50:
            return "suspend"        # блок на 7 дней
        if avg_pnl < 0 and trades >= 30:
            return "shadow"         # в тень, не исполняем
        if win_rate < 0.40 and trades >= 30:
            return "reduce_size"    # размер -50%
        return None

    # --- helpers ---
    def _features_to_vector(self, features_list: List[dict]):
        KEYS = ["rr_ratio", "sl_distance_pct", "tp_distance_pct",
                "leverage", "source_win_rate", "funding_rate",
                "volume_ratio", "market_regime_bull"]
        import numpy as np
        rows = []
        for f in features_list:
            row = [float(f.get(k, 0) or 0) for k in KEYS]
            rows.append(row)
        return np.array(rows, dtype=float)

    def _save_record(self, rec: ModelRecord) -> None:
        path = MODELS_DIR / "records.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(vars(rec)) + "\n")

    def _load_champions(self) -> None:
        for pkl in MODELS_DIR.glob("*_v*.pkl"):
            try:
                source = pkl.stem.rsplit("_v", 1)[0]
                with open(pkl, "rb") as f:
                    model = pickle.load(f)
                self._champions[source] = model
                log.info("Loaded champion for %s from %s", source, pkl.name)
            except Exception as e:
                log.warning("Failed to load model %s: %s", pkl, e)


cc_engine = ChampionChallenger()
