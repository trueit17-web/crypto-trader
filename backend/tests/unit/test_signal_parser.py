"""Unit tests for SignalParser."""
import pytest
from decimal import Decimal
from app.signal.parser import SignalParser, ParsedSignal


@pytest.fixture
def parser():
    return SignalParser()


class TestStructuredSignals:
    def test_long_with_full_fields(self, parser):
        text = """
        📊 BTC/USDT LONG
        🔑 Вход: 43000-43500
        🛑 Стоп: 42000
        🎯 TP1: 45000 | TP2: 47000 | TP3: 50000
        📈 Плечо: 10x
        """
        sig = parser.parse(text)
        assert sig is not None
        assert sig.symbol == 'BTC/USDT'
        assert sig.direction == 'long'
        assert sig.entry_min == Decimal('43000')
        assert sig.entry_max == Decimal('43500')
        assert sig.stop_loss == Decimal('42000')
        assert Decimal('45000') in sig.take_profits
        assert Decimal('47000') in sig.take_profits
        assert sig.leverage == 10

    def test_short_signal(self, parser):
        text = 'ETH/USDT SHORT вход: 3100 sl: 3200 tp1: 2900'
        sig = parser.parse(text)
        assert sig is not None
        assert sig.direction == 'short'
        assert sig.symbol == 'ETH/USDT'

    def test_english_buy(self, parser):
        text = 'SOL/USDT buy entry 160-165 stop 150 target 180'
        sig = parser.parse(text)
        assert sig is not None
        assert sig.direction == 'long'
        assert sig.symbol == 'SOL/USDT'

    def test_missing_symbol_returns_none(self, parser):
        text = 'long вход: 43000 sl: 42000'
        sig = parser.parse(text)
        assert sig is None

    def test_missing_direction_returns_none(self, parser):
        text = 'BTC/USDT вход: 43000 sl: 42000'
        sig = parser.parse(text)
        assert sig is None

    def test_cancel_signal(self, parser):
        text = 'BTC/USDT cancel signal'
        sig = parser.parse(text)
        assert sig is not None
        assert sig.signal_type == 'cancel'

    def test_entry_price_midpoint(self, parser):
        text = 'BTC/USDT long вход: 43000-43500'
        sig = parser.parse(text)
        assert sig is not None
        assert sig.entry_price == Decimal('43250')

    def test_sl_distance_calculation(self, parser):
        text = 'BTC/USDT long вход: 43000 sl: 42000'
        sig = parser.parse(text)
        assert sig is not None
        dist = sig.stop_loss_distance_pct
        assert dist is not None
        assert abs(dist - 1000/43000) < 0.001


class TestRiskMetrics:
    def test_risk_reward(self, parser):
        text = 'BTC/USDT long вход: 43000 sl: 42000 tp1: 45000'
        sig = parser.parse(text)
        assert sig is not None
        rr = sig.risk_reward
        assert rr is not None
        assert abs(rr - 2.0) < 0.01   # (45000-43000) / (43000-42000)

    def test_no_rr_without_sl(self, parser):
        text = 'BTC/USDT long вход: 43000 tp1: 45000'
        sig = parser.parse(text)
        assert sig is not None
        assert sig.risk_reward is None
