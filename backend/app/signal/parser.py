"""Signal parser: regex + NLP (Section D of spec)."""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedSignal:
    symbol: str
    direction: str          # long | short
    entry_min: Optional[Decimal] = None
    entry_max: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profits: list[Decimal] = field(default_factory=list)
    leverage: Optional[int] = None
    timeframe: Optional[str] = None
    signal_type: str = 'entry'  # entry | update | close | cancel
    confidence: dict = field(default_factory=dict)
    raw_text: str = ''

    @property
    def entry_price(self) -> Optional[Decimal]:
        """Midpoint of entry range."""
        if self.entry_min and self.entry_max:
            return (self.entry_min + self.entry_max) / 2
        return self.entry_min or self.entry_max

    @property
    def stop_loss_distance_pct(self) -> Optional[float]:
        ep = self.entry_price
        if ep and self.stop_loss and ep != 0:
            return abs(float(ep - self.stop_loss) / float(ep))
        return None

    @property
    def risk_reward(self) -> Optional[float]:
        """R:R using first TP."""
        ep = self.entry_price
        if ep and self.stop_loss and self.take_profits:
            risk = abs(float(ep - self.stop_loss))
            reward = abs(float(self.take_profits[0] - ep))
            if risk > 0:
                return reward / risk
        return None


class SignalParser:
    """Rule-based signal parser with confidence scoring."""

    # --- Direction ---
    _DIR = {
        'long':  re.compile(r'\b(long|buy|покупк|лонг|купить|бай)\b', re.I),
        'short': re.compile(r'\b(short|sell|продаж|шорт|продать|сел)\b', re.I),
    }

    # --- Cancel / close keywords ---
    _CANCEL = re.compile(
        r'\b(cancel|отмен|close|закрыт|стоп сигнал|signal closed)\b', re.I
    )

    # --- Symbol: e.g. BTC/USDT, ETHUSDT, SOL-PERP ---
    _SYMBOL = re.compile(
        r'\b([A-Z]{2,10})[/\-_]?(USDT|USD|BTC|ETH|BUSD|USDC)(?:[/\-_]?(?:PERP|SWAP|FUTURES))?\b',
        re.I,
    )

    # --- Prices ---
    _ENTRY = re.compile(
        r'(?:вход|entry|enter|zone|зона)[:\s]+([\d,\.]+(?:\s*[-–]\s*[\d,\.]+)?)',
        re.I,
    )
    _SL = re.compile(
        r'(?:\bsl\b|стоп[-\s]?лосс?|stop[-\s]?loss?)[:\s]+([\d,\.]+)',
        re.I,
    )
    _TP = re.compile(
        r'(?:tp\d?|цель\d?|target\d?|take\s*profit\d?)[:\s]+([\d,\.]+)',
        re.I,
    )
    _LEV = re.compile(
        r'(?:плечо|leverage|lev)[:\s×x]*(\d+)[×x]?|x(\d+)\b',
        re.I,
    )
    _TF = re.compile(
        r'(?:tf|timeframe|таймфрейм)[:\s]*(\d+[mhd]|\d+\s*(?:min|hour|day))',
        re.I,
    )

    def _clean_price(self, s: str) -> Optional[Decimal]:
        s = s.replace(',', '.').strip()
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    def _parse_range(self, s: str) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Parse '43000' or '43000-43500'."""
        parts = re.split(r'[-–]', s.strip())
        if len(parts) == 2:
            lo = self._clean_price(parts[0])
            hi = self._clean_price(parts[1])
            if lo and hi:
                return (min(lo, hi), max(lo, hi))
        p = self._clean_price(parts[0])
        return (p, p)

    def parse(self, text: str) -> Optional[ParsedSignal]:
        confidence: dict[str, float] = {}
        sig = ParsedSignal(raw_text=text, symbol='', direction='')

        # --- Cancel / close ---
        if self._CANCEL.search(text):
            sig.signal_type = 'cancel'
            confidence['signal_type'] = 0.85

        # --- Direction ---
        for direction, pat in self._DIR.items():
            if pat.search(text):
                sig.direction = direction
                confidence['direction'] = 0.90
                break

        # --- Symbol ---
        m = self._SYMBOL.search(text)
        if m:
            base = m.group(1).upper()
            quote = m.group(2).upper()
            sig.symbol = f'{base}/{quote}'
            confidence['symbol'] = 0.95

        # --- Entry ---
        m = self._ENTRY.search(text)
        if m:
            lo, hi = self._parse_range(m.group(1))
            sig.entry_min = lo
            sig.entry_max = hi
            confidence['entry'] = 0.90 if lo != hi else 0.80

        # --- Stop loss ---
        m = self._SL.search(text)
        if m:
            sig.stop_loss = self._clean_price(m.group(1))
            if sig.stop_loss:
                confidence['stop_loss'] = 0.90

        # --- Take profits (multiple) ---
        for m in self._TP.finditer(text):
            p = self._clean_price(m.group(1))
            if p:
                sig.take_profits.append(p)
        if sig.take_profits:
            confidence['take_profits'] = 0.85

        # --- Leverage ---
        m = self._LEV.search(text)
        if m:
            lev_str = m.group(1) or m.group(2)
            if lev_str:
                sig.leverage = int(lev_str)
                confidence['leverage'] = 0.90

        # --- Timeframe ---
        m = self._TF.search(text)
        if m:
            sig.timeframe = m.group(1)
            confidence['timeframe'] = 0.80

        sig.confidence = confidence

        # Minimum viable signal: symbol + direction
        if not sig.symbol or not sig.direction:
            logger.debug('Signal parse failed: missing symbol or direction')
            return None

        return sig


__all__ = ['SignalParser', 'ParsedSignal']
