"""Signal hard-gate validation (Section D of spec)."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional
import logging
from datetime import datetime, timezone

from app.signal.parser import ParsedSignal

logger = logging.getLogger(__name__)


class ValidationResult(Enum):
    PASS   = 'pass'
    REJECT = 'reject'
    DELAY  = 'delay'


@dataclass
class ValidationOutcome:
    result: ValidationResult
    reason: str


class SignalValidator:
    """
    Applies hard gates from Section D.
    All gates must pass before the signal enters scoring.
    """

    def __init__(self, config: Optional[dict] = None):
        self.cfg = {
            'max_leverage': 10,
            'max_sl_distance_pct': 0.30,
            'min_rr': 0.5,
            'max_age_minutes': 30,
            'min_volume_usd_24h': 10_000_000,
            **( config or {}),
        }

    def validate(self, signal: ParsedSignal, received_at: Optional[datetime] = None) -> ValidationOutcome:
        now = datetime.now(timezone.utc)

        # --- 1. Symbol exists (caller must verify against exchange instrument list) ---
        if not signal.symbol:
            return ValidationOutcome(ValidationResult.REJECT, 'Empty symbol')

        # --- 2. Leverage ---
        if signal.leverage and signal.leverage > self.cfg['max_leverage']:
            return ValidationOutcome(
                ValidationResult.REJECT,
                f'Leverage {signal.leverage}x > max {self.cfg["max_leverage"]}x',
            )

        # --- 3. Stop-loss distance ---
        sl_dist = signal.stop_loss_distance_pct
        if sl_dist is not None and sl_dist > self.cfg['max_sl_distance_pct']:
            return ValidationOutcome(
                ValidationResult.REJECT,
                f'SL distance {sl_dist:.1%} > max {self.cfg["max_sl_distance_pct"]:.0%}',
            )

        # --- 4. Risk-reward ---
        rr = signal.risk_reward
        if rr is not None and rr < self.cfg['min_rr']:
            return ValidationOutcome(
                ValidationResult.REJECT,
                f'R:R {rr:.2f} < min {self.cfg["min_rr"]}',
            )

        # --- 5. Signal age ---
        if received_at:
            age_minutes = (now - received_at).total_seconds() / 60
            if age_minutes > self.cfg['max_age_minutes']:
                return ValidationOutcome(
                    ValidationResult.REJECT,
                    f'Signal is {age_minutes:.0f}m old (max {self.cfg["max_age_minutes"]}m)',
                )

        return ValidationOutcome(ValidationResult.PASS, 'All hard gates passed')
