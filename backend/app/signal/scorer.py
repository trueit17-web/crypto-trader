"""Signal and source scoring (Section D of spec)."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

from app.signal.parser import ParsedSignal
from app.core.events import SignalDecision


@dataclass
class ScoreBreakdown:
    source_score: float       # 0.0 – 1.0
    signal_score: float       # 0.0 – 1.0
    final_score: float        # 0.4*source + 0.6*signal
    decision: SignalDecision
    size_fraction: float      # 0.0 – 1.0
    reasons: dict


class SignalScorer:
    """
    Computes source + signal quality scores and maps to a decision.

    Source score: built from historical win rate, R:R, sample size.
    Signal score: completeness, R:R realism, liquidity proxy.
    """

    SOURCE_WEIGHT = 0.4
    SIGNAL_WEIGHT = 0.6

    # Decision thresholds
    APPROVE_FULL   = 0.75
    APPROVE_HALF   = 0.55
    DELAY_FLOOR    = 0.40

    def score(
        self,
        signal: ParsedSignal,
        *,
        source_win_rate: float = 0.5,
        source_signal_count: int = 0,
        source_avg_rr: float = 1.0,
        is_paper_only: bool = False,
        volatility_multiplier: float = 1.0,
    ) -> ScoreBreakdown:
        reasons: dict = {}

        # --- Source score ---
        src = self._source_score(
            win_rate=source_win_rate,
            avg_rr=source_avg_rr,
            signal_count=source_signal_count,
        )
        reasons['source'] = {
            'win_rate': source_win_rate,
            'avg_rr': source_avg_rr,
            'signal_count': source_signal_count,
            'score': src,
        }

        # --- Signal score ---
        sig = self._signal_score(signal, volatility_multiplier)
        reasons['signal'] = {'score': sig}

        # --- Final ---
        final = self.SOURCE_WEIGHT * src + self.SIGNAL_WEIGHT * sig
        reasons['final'] = final

        # --- Decision ---
        if is_paper_only:
            decision = SignalDecision.PAPER_ONLY
            size_fraction = 1.0
        elif final >= self.APPROVE_FULL:
            decision = SignalDecision.APPROVE
            size_fraction = 1.0
        elif final >= self.APPROVE_HALF:
            decision = SignalDecision.APPROVE
            size_fraction = 0.5
        elif final >= self.DELAY_FLOOR:
            decision = SignalDecision.DELAY
            size_fraction = 0.5
        else:
            decision = SignalDecision.REJECT
            size_fraction = 0.0

        return ScoreBreakdown(
            source_score=src,
            signal_score=sig,
            final_score=final,
            decision=decision,
            size_fraction=size_fraction,
            reasons=reasons,
        )

    def _source_score(self, win_rate: float, avg_rr: float, signal_count: int) -> float:
        # Confidence grows with sample size (min 50 signals for full trust)
        sample_factor = min(signal_count / 50, 1.0) if signal_count > 0 else 0.1

        # Base = win_rate weighted by sample factor
        base = win_rate * sample_factor

        # R:R bonus: good R:R compensates for lower win rate
        rr_bonus = min(avg_rr / 3.0, 0.3)

        return min(base + rr_bonus, 1.0)

    def _signal_score(self, signal: ParsedSignal, vol_mult: float) -> float:
        score = 0.0

        # Completeness
        completeness = sum([
            bool(signal.symbol),
            bool(signal.direction),
            signal.entry_min is not None,
            signal.stop_loss is not None,
            bool(signal.take_profits),
        ]) / 5.0
        score += completeness * 0.4

        # R:R realism
        rr = signal.risk_reward
        if rr and 0.5 <= rr <= 5.0:
            score += 0.3
        elif rr and rr > 0:
            score += 0.1

        # Volatility penalty (high vol reduces score)
        vol_penalty = max(0, (vol_mult - 1.0) * 0.1)
        score -= vol_penalty

        # SL present and reasonable
        sl_dist = signal.stop_loss_distance_pct
        if sl_dist and 0.005 <= sl_dist <= 0.15:
            score += 0.3
        elif signal.stop_loss:
            score += 0.1

        return max(0.0, min(score, 1.0))
