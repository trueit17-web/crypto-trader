"""
Walk-Forward Test — роллинг-виндоу бэктест для избежания overfitting.
Разбивает данные на in-sample/out-of-sample окна и оценивает стабильность стратегии.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class WFWindow:
    idx: int
    train_start: int   # индекс в датасете
    train_end: int
    test_start: int
    test_end: int


@dataclass
class WFResult:
    window: WFWindow
    in_sample_sharpe: Optional[float]
    out_of_sample_sharpe: Optional[float]
    in_sample_pnl: float
    out_of_sample_pnl: float
    in_sample_win_rate: Optional[float]
    out_of_sample_win_rate: Optional[float]
    best_params: Dict[str, Any] = field(default_factory=dict)
    efficiency: Optional[float] = None   # oos_sharpe / is_sharpe


@dataclass
class WFConfig:
    n_windows: int = 5           # количество окон
    train_pct: float = 0.7       # 70% на обучение
    anchored: bool = False       # True = окно растёт от начала
    min_trades_per_window: int = 10


class WalkForwardAnalyzer:
    """
    Запускает walk-forward анализ на любом наборе ордеров/сигналов.

    backtest_fn(data, params) -> {trades, pnl_pct_series, win_rate, sharpe}
    """

    def __init__(self, config: Optional[WFConfig] = None):
        self.config = config or WFConfig()

    def run(self,
            data: List[Any],
            backtest_fn: Callable,
            param_grid: Optional[List[Dict]] = None,
            ) -> List[WFResult]:
        """
        Строит разбивку данных, для каждого окна:
          1. Оптимизирует params на in-sample
          2. Оценивает на out-of-sample
          3. Пишет WFResult
        """
        cfg = self.config
        n = len(data)
        windows = self._build_windows(n)
        results = []
        default_params = param_grid[0] if param_grid else {}

        for w in windows:
            train_data = data[w.train_start:w.train_end]
            test_data = data[w.test_start:w.test_end]

            # Оптимизация на in-sample
            best_params = default_params
            best_is_result = backtest_fn(train_data, default_params)
            if param_grid and len(param_grid) > 1:
                best_is_sharpe = best_is_result.get("sharpe") or -999
                for params in param_grid[1:]:
                    res = backtest_fn(train_data, params)
                    s = res.get("sharpe") or -999
                    if s > best_is_sharpe:
                        best_is_sharpe = s
                        best_params = params
                        best_is_result = res

            # Оценка на out-of-sample
            oos_result = backtest_fn(test_data, best_params)

            is_sharpe = best_is_result.get("sharpe")
            oos_sharpe = oos_result.get("sharpe")
            efficiency = None
            if is_sharpe and oos_sharpe and is_sharpe != 0:
                efficiency = oos_sharpe / is_sharpe

            wf_res = WFResult(
                window=w,
                in_sample_sharpe=is_sharpe,
                out_of_sample_sharpe=oos_sharpe,
                in_sample_pnl=best_is_result.get("total_pnl", 0),
                out_of_sample_pnl=oos_result.get("total_pnl", 0),
                in_sample_win_rate=best_is_result.get("win_rate"),
                out_of_sample_win_rate=oos_result.get("win_rate"),
                best_params=best_params,
                efficiency=efficiency,
            )
            results.append(wf_res)
            log.info("WF window=%d IS_sharpe=%.2f OOS_sharpe=%.2f eff=%.2f",
                     w.idx,
                     is_sharpe or 0,
                     oos_sharpe or 0,
                     efficiency or 0)

        return results

    def _build_windows(self, n: int) -> List[WFWindow]:
        cfg = self.config
        windows = []
        step = n // cfg.n_windows

        for i in range(cfg.n_windows):
            if cfg.anchored:
                train_start = 0
                train_end = int(step * (i + 1) * cfg.train_pct)
            else:
                train_start = i * step
                train_end = train_start + int(step * cfg.train_pct)

            test_start = train_end
            test_end = min(train_start + step * (1 if not cfg.anchored else (i + 1)), n)

            if test_end > test_start and train_end > train_start:
                windows.append(WFWindow(
                    idx=i,
                    train_start=train_start, train_end=train_end,
                    test_start=test_start, test_end=test_end,
                ))
        return windows

    @staticmethod
    def summary(results: List[WFResult]) -> dict:
        """Сводная статистика по всем окнам."""
        oos_sharpes = [r.out_of_sample_sharpe for r in results
                       if r.out_of_sample_sharpe is not None]
        effs = [r.efficiency for r in results if r.efficiency is not None]
        oos_pnls = [r.out_of_sample_pnl for r in results]
        return {
            "n_windows": len(results),
            "avg_oos_sharpe": sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else None,
            "avg_efficiency": sum(effs) / len(effs) if effs else None,
            "total_oos_pnl": sum(oos_pnls),
            "profitable_windows": sum(1 for p in oos_pnls if p > 0),
            "is_robust": (sum(effs) / len(effs) > 0.5) if effs else None,
        }
