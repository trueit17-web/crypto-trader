"""All SQLAlchemy ORM models (Section J of spec)."""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DECIMAL, BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def utcnow():
    return func.timezone('UTC', func.now())


# ===========================================================================
# AUTH
# ===========================================================================
class User(Base):
    __tablename__ = 'users'

    id:            Mapped[str]  = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    email:         Mapped[str]  = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str]  = mapped_column(String(255), nullable=False)
    totp_secret:   Mapped[Optional[str]] = mapped_column(String(64))
    role:          Mapped[str]  = mapped_column(String(20), nullable=False, default='viewer')  # viewer|analyst|trader|admin
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class ApiKey(Base):
    __tablename__ = 'api_keys'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    user_id:     Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    key_hash:    Mapped[str] = mapped_column(String(128), nullable=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list)
    last_used_at:Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at:  Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Session(Base):
    __tablename__ = 'sessions'

    id:                  Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    user_id:             Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    refresh_token_hash:  Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address:          Mapped[Optional[str]] = mapped_column(String(45))
    created_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    expires_at:          Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ===========================================================================
# EXCHANGES
# ===========================================================================
class Exchange(Base):
    __tablename__ = 'exchanges'

    id:            Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    name:          Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    adapter_class: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json:   Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class ExchangeCredential(Base):
    __tablename__ = 'exchange_credentials'

    id:                   Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    user_id:              Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    exchange_id:          Mapped[str] = mapped_column(ForeignKey('exchanges.id', ondelete='CASCADE'))
    encrypted_api_key:    Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_secret:     Mapped[str] = mapped_column(Text, nullable=False)
    permissions_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:           Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Instrument(Base):
    __tablename__ = 'instruments'

    id:              Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    exchange_id:     Mapped[str] = mapped_column(ForeignKey('exchanges.id', ondelete='CASCADE'))
    symbol_normalized: Mapped[str] = mapped_column(String(30), nullable=False)  # BTC/USDT
    symbol_native:   Mapped[str] = mapped_column(String(30), nullable=False)    # BTCUSDT
    market_type:     Mapped[str] = mapped_column(String(20), nullable=False)    # spot|perp|margin
    tick_size:       Mapped[Decimal] = mapped_column(DECIMAL(20, 10))
    lot_size:        Mapped[Decimal] = mapped_column(DECIMAL(20, 10))
    min_notional:    Mapped[Decimal] = mapped_column(DECIMAL(20, 4))
    max_leverage:    Mapped[int] = mapped_column(Integer, default=1)
    is_active:       Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow(), onupdate=utcnow())


# ===========================================================================
# MARKET DATA  (TimescaleDB hypertables — created via raw SQL in migration)
# ===========================================================================
class Candle(Base):
    __tablename__ = 'candles'

    time:         Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    exchange_id:  Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol:       Mapped[str] = mapped_column(String(30), primary_key=True)
    timeframe:    Mapped[str] = mapped_column(String(5), primary_key=True)   # 1m|5m|15m|1h|4h|1d
    open:         Mapped[Decimal] = mapped_column(DECIMAL(24, 8))
    high:         Mapped[Decimal] = mapped_column(DECIMAL(24, 8))
    low:          Mapped[Decimal] = mapped_column(DECIMAL(24, 8))
    close:        Mapped[Decimal] = mapped_column(DECIMAL(24, 8))
    volume:       Mapped[Decimal] = mapped_column(DECIMAL(30, 8))
    quote_volume: Mapped[Decimal] = mapped_column(DECIMAL(30, 8))


class FundingRate(Base):
    __tablename__ = 'funding_rates'

    time:        Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    exchange_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol:      Mapped[str] = mapped_column(String(30), primary_key=True)
    rate:        Mapped[Decimal] = mapped_column(DECIMAL(20, 10))


# ===========================================================================
# TELEGRAM
# ===========================================================================
class TelegramSource(Base):
    __tablename__ = 'telegram_sources'

    id:           Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    name:         Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id:   Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    is_authorized:Mapped[bool] = mapped_column(Boolean, default=False)
    is_paper_only:Mapped[bool] = mapped_column(Boolean, default=True)
    quality_score:Mapped[float] = mapped_column(DECIMAL(4, 3), default=0.5)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    win_rate:     Mapped[float] = mapped_column(DECIMAL(4, 3), default=0.0)
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class RawMessage(Base):
    __tablename__ = 'raw_messages'

    id:           Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    source_id:    Mapped[str] = mapped_column(ForeignKey('telegram_sources.id', ondelete='CASCADE'))
    message_id:   Mapped[int] = mapped_column(BigInteger, nullable=False)
    chat_id:      Mapped[int] = mapped_column(BigInteger, nullable=False)
    text:         Mapped[str] = mapped_column(Text, default='')
    edit_date:    Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    received_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)


class ParsedSignal(Base):
    __tablename__ = 'parsed_signals'

    id:             Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    raw_message_id: Mapped[str] = mapped_column(ForeignKey('raw_messages.id', ondelete='CASCADE'))
    symbol:         Mapped[str] = mapped_column(String(30), nullable=False)
    direction:      Mapped[str] = mapped_column(String(10), nullable=False)  # long|short
    entry_min:      Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    entry_max:      Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    stop_loss:      Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    take_profits:   Mapped[list] = mapped_column(JSONB, default=list)
    leverage:       Mapped[Optional[int]] = mapped_column(Integer)
    expiry_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confidence:     Mapped[dict] = mapped_column(JSONB, default=dict)
    parsed_at:      Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class SignalScore(Base):
    __tablename__ = 'signal_scores'

    id:               Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    parsed_signal_id: Mapped[str] = mapped_column(ForeignKey('parsed_signals.id', ondelete='CASCADE'))
    source_score:     Mapped[float] = mapped_column(DECIMAL(4, 3))
    signal_score:     Mapped[float] = mapped_column(DECIMAL(4, 3))
    final_score:      Mapped[float] = mapped_column(DECIMAL(4, 3))
    decision:         Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVE|REDUCE_SIZE|DELAY|PAPER_ONLY|REJECT
    decision_reason:  Mapped[dict] = mapped_column(JSONB, default=dict)
    size_fraction:    Mapped[float] = mapped_column(DECIMAL(4, 3), default=1.0)
    reviewed_by:      Mapped[Optional[str]] = mapped_column(ForeignKey('users.id'))
    reviewed_at:      Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# STRATEGIES
# ===========================================================================
class Strategy(Base):
    __tablename__ = 'strategies'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    name:        Mapped[str] = mapped_column(String(100), nullable=False)
    class_name:  Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active:   Mapped[bool] = mapped_column(Boolean, default=False)
    mode:        Mapped[str] = mapped_column(String(20), default='paper')  # paper|shadow|live
    exchange_id: Mapped[Optional[str]] = mapped_column(ForeignKey('exchanges.id'))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# ORDERS & FILLS
# ===========================================================================
class Order(Base):
    __tablename__ = 'orders'

    id:                Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    client_order_id:   Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(64))
    exchange_id:       Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    symbol:            Mapped[str] = mapped_column(String(30), nullable=False)
    side:              Mapped[str] = mapped_column(String(5), nullable=False)   # buy|sell
    order_type:        Mapped[str] = mapped_column(String(20), nullable=False)  # market|limit|...
    quantity:          Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    price:             Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    status:            Mapped[str] = mapped_column(String(20), default='open')
    source_type:       Mapped[str] = mapped_column(String(20), default='manual')  # signal|strategy|manual
    source_id:         Mapped[Optional[str]] = mapped_column(String(36))
    strategy_id:       Mapped[Optional[str]] = mapped_column(ForeignKey('strategies.id'))
    signal_decision_id:Mapped[Optional[str]] = mapped_column(ForeignKey('signal_scores.id'))
    idempotency_key:   Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    updated_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow(), onupdate=utcnow())


class Fill(Base):
    __tablename__ = 'fills'

    id:           Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    order_id:     Mapped[str] = mapped_column(ForeignKey('orders.id', ondelete='CASCADE'))
    fill_id:      Mapped[str] = mapped_column(String(64), nullable=False)
    price:        Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    quantity:     Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    fee:          Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=0)
    fee_currency: Mapped[str] = mapped_column(String(10), default='USDT')
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    is_maker:     Mapped[bool] = mapped_column(Boolean, default=False)


# ===========================================================================
# POSITIONS & BALANCES
# ===========================================================================
class Position(Base):
    __tablename__ = 'positions'

    id:                Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    exchange_id:       Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    symbol:            Mapped[str] = mapped_column(String(30), nullable=False)
    side:              Mapped[str] = mapped_column(String(5), nullable=False)  # long|short
    quantity:          Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    entry_price:       Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    margin_mode:       Mapped[str] = mapped_column(String(10), default='isolated')
    leverage:          Mapped[int] = mapped_column(Integer, default=1)
    unrealized_pnl:    Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    liquidation_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    opened_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    updated_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow(), onupdate=utcnow())


class Balance(Base):
    __tablename__ = 'balances'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    exchange_id: Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    currency:    Mapped[str] = mapped_column(String(10), nullable=False)
    total:       Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    available:   Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    locked:      Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow(), onupdate=utcnow())


class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshots'

    id:              Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    timestamp:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    total_equity:    Mapped[Decimal] = mapped_column(DECIMAL(24, 4))
    unrealized_pnl:  Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    realized_pnl_day:Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    nav_json:        Mapped[dict] = mapped_column(JSONB, default=dict)


# ===========================================================================
# RISK
# ===========================================================================
class RiskEventModel(Base):
    __tablename__ = 'risk_events'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    event_type:  Mapped[str] = mapped_column(String(50), nullable=False)
    severity:    Mapped[str] = mapped_column(String(10), nullable=False)  # info|warning|critical
    component:   Mapped[str] = mapped_column(String(50))
    details:     Mapped[dict] = mapped_column(JSONB, default=dict)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class RiskConfig(Base):
    __tablename__ = 'risk_config'

    id:         Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    scope:      Mapped[str] = mapped_column(String(20))    # global|exchange|strategy|source
    scope_id:   Mapped[Optional[str]] = mapped_column(String(36))
    param_name: Mapped[str] = mapped_column(String(60), nullable=False)
    param_value:Mapped[str] = mapped_column(String(100), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow(), onupdate=utcnow())


# ===========================================================================
# ML & BACKTESTS
# ===========================================================================
class MlModel(Base):
    __tablename__ = 'ml_models'

    id:            Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    name:          Mapped[str] = mapped_column(String(100), nullable=False)
    version:       Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm:     Mapped[str] = mapped_column(String(50))
    features_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics_json:  Mapped[dict] = mapped_column(JSONB, default=dict)
    status:        Mapped[str] = mapped_column(String(20), default='training')  # training|challenger|champion|retired
    champion_since:Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class BacktestRun(Base):
    __tablename__ = 'backtest_runs'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    strategy_id: Mapped[Optional[str]] = mapped_column(ForeignKey('strategies.id'))
    model_id:    Mapped[Optional[str]] = mapped_column(ForeignKey('ml_models.id'))
    from_date:   Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_date:     Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    results_json:Mapped[dict] = mapped_column(JSONB, default=dict)
    status:      Mapped[str] = mapped_column(String(20), default='pending')  # pending|running|done|failed
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# AUDIT (append-only — protected by trigger in migration)
# ===========================================================================
class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id:          Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text('gen_random_uuid()'))
    event_type:  Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id:    Mapped[Optional[str]] = mapped_column(String(36))
    component:   Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id:   Mapped[Optional[str]] = mapped_column(String(36))
    details:     Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address:  Mapped[Optional[str]] = mapped_column(String(45))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
