"""All SQLAlchemy ORM models."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DECIMAL, BigInteger, Boolean, DateTime, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow():
    return func.timezone('UTC', func.now())


# ===========================================================================
# AUTH
# ===========================================================================
class User(Base):
    __tablename__ = 'users'

    id:            Mapped[str]  = mapped_column(String(36), primary_key=True, default=new_uuid)
    email:         Mapped[str]  = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str]  = mapped_column(String(255), nullable=False)
    totp_secret:   Mapped[Optional[str]] = mapped_column(String(64))
    role:          Mapped[str]  = mapped_column(String(20), nullable=False, default='viewer')
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class ApiKey(Base):
    __tablename__ = 'api_keys'

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id:      Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    key_hash:     Mapped[str] = mapped_column(String(128), nullable=False)
    permissions:  Mapped[list] = mapped_column(JSONB, default=list)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at:   Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Session(Base):
    __tablename__ = 'sessions'

    id:                 Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id:            Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    refresh_token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    ip_address:         Mapped[Optional[str]] = mapped_column(String(45))
    created_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    expires_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ===========================================================================
# EXCHANGES
# ===========================================================================
class Exchange(Base):
    __tablename__ = 'exchanges'

    id:            Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name:          Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    adapter_class: Mapped[str] = mapped_column(String(100), nullable=False)
    config_json:   Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active:     Mapped[bool] = mapped_column(Boolean, default=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class ExchangeCredential(Base):
    __tablename__ = 'exchange_credentials'

    id:                   Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id:              Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    exchange_id:          Mapped[str] = mapped_column(ForeignKey('exchanges.id', ondelete='CASCADE'))
    encrypted_api_key:    Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_secret:     Mapped[str] = mapped_column(Text, nullable=False)
    permissions_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:           Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Instrument(Base):
    __tablename__ = 'instruments'

    id:               Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    exchange_id:      Mapped[str] = mapped_column(ForeignKey('exchanges.id', ondelete='CASCADE'))
    symbol_normalized:Mapped[str] = mapped_column(String(30), nullable=False)
    symbol_native:    Mapped[str] = mapped_column(String(30), nullable=False)
    market_type:      Mapped[str] = mapped_column(String(20), nullable=False)
    tick_size:        Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 10))
    lot_size:         Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 10))
    min_notional:     Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 4))
    max_leverage:     Mapped[int] = mapped_column(Integer, default=1)
    is_active:        Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at:       Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# MARKET DATA
# ===========================================================================
class Candle(Base):
    __tablename__ = 'candles'

    time:         Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    exchange_id:  Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol:       Mapped[str] = mapped_column(String(30), primary_key=True)
    timeframe:    Mapped[str] = mapped_column(String(5), primary_key=True)
    open:         Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    high:         Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    low:          Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    close:        Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    volume:       Mapped[Optional[Decimal]] = mapped_column(DECIMAL(30, 8))
    quote_volume: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(30, 8))


class FundingRate(Base):
    __tablename__ = 'funding_rates'

    time:        Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    exchange_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    symbol:      Mapped[str] = mapped_column(String(30), primary_key=True)
    rate:        Mapped[Optional[Decimal]] = mapped_column(DECIMAL(20, 10))


# ===========================================================================
# TELEGRAM
# ===========================================================================
class TelegramSource(Base):
    __tablename__ = 'telegram_sources'

    id:            Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name:          Mapped[str] = mapped_column(String(255), nullable=False)
    channel_id:    Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    is_authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paper_only: Mapped[bool] = mapped_column(Boolean, default=True)
    quality_score: Mapped[float] = mapped_column(DECIMAL(4, 3), default=0.5)
    signal_count:  Mapped[int] = mapped_column(Integer, default=0)
    win_rate:      Mapped[float] = mapped_column(DECIMAL(4, 3), default=0.0)
    created_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class RawMessage(Base):
    __tablename__ = 'raw_messages'

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
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

    id:             Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    raw_message_id: Mapped[str] = mapped_column(ForeignKey('raw_messages.id', ondelete='CASCADE'))
    symbol:         Mapped[str] = mapped_column(String(30), nullable=False)
    direction:      Mapped[str] = mapped_column(String(10), nullable=False)
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

    id:               Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    parsed_signal_id: Mapped[str] = mapped_column(ForeignKey('parsed_signals.id', ondelete='CASCADE'))
    source_score:     Mapped[float] = mapped_column(DECIMAL(4, 3))
    signal_score:     Mapped[float] = mapped_column(DECIMAL(4, 3))
    final_score:      Mapped[float] = mapped_column(DECIMAL(4, 3))
    decision:         Mapped[str] = mapped_column(String(20), nullable=False)
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

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name:        Mapped[str] = mapped_column(String(100), nullable=False)
    class_name:  Mapped[str] = mapped_column(String(100), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active:   Mapped[bool] = mapped_column(Boolean, default=False)
    mode:        Mapped[str] = mapped_column(String(20), default='paper')
    exchange_id: Mapped[Optional[str]] = mapped_column(ForeignKey('exchanges.id'))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# ORDERS & FILLS
# ===========================================================================
class Order(Base):
    __tablename__ = 'orders'

    id:                 Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    client_order_id:    Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exchange_order_id:  Mapped[Optional[str]] = mapped_column(String(64))
    exchange_id:        Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    symbol:             Mapped[str] = mapped_column(String(30), nullable=False)
    side:               Mapped[str] = mapped_column(String(5), nullable=False)
    order_type:         Mapped[str] = mapped_column(String(20), nullable=False)
    quantity:           Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    price:              Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    status:             Mapped[str] = mapped_column(String(20), default='open')
    source_type:        Mapped[str] = mapped_column(String(20), default='manual')
    source_id:          Mapped[Optional[str]] = mapped_column(String(36))
    strategy_id:        Mapped[Optional[str]] = mapped_column(ForeignKey('strategies.id'))
    signal_decision_id: Mapped[Optional[str]] = mapped_column(ForeignKey('signal_scores.id'))
    idempotency_key:    Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    updated_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Fill(Base):
    __tablename__ = 'fills'

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
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

    id:                Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    exchange_id:       Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    symbol:            Mapped[str] = mapped_column(String(30), nullable=False)
    side:              Mapped[str] = mapped_column(String(5), nullable=False)
    quantity:          Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    entry_price:       Mapped[Decimal] = mapped_column(DECIMAL(24, 8), nullable=False)
    margin_mode:       Mapped[str] = mapped_column(String(10), default='isolated')
    leverage:          Mapped[int] = mapped_column(Integer, default=1)
    unrealized_pnl:    Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    liquidation_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(24, 8))
    opened_at:         Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    updated_at:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class Balance(Base):
    __tablename__ = 'balances'

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    exchange_id: Mapped[str] = mapped_column(ForeignKey('exchanges.id'))
    currency:    Mapped[str] = mapped_column(String(10), nullable=False)
    total:       Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    available:   Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    locked:      Mapped[Decimal] = mapped_column(DECIMAL(24, 8), default=0)
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshots'

    id:               Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    timestamp:        Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
    total_equity:     Mapped[Decimal] = mapped_column(DECIMAL(24, 4))
    unrealized_pnl:   Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    realized_pnl_day: Mapped[Decimal] = mapped_column(DECIMAL(20, 4), default=0)
    nav_json:         Mapped[dict] = mapped_column(JSONB, default=dict)


# ===========================================================================
# RISK
# ===========================================================================
class RiskEventModel(Base):
    __tablename__ = 'risk_events'

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_type:  Mapped[str] = mapped_column(String(50), nullable=False)
    severity:    Mapped[str] = mapped_column(String(10), nullable=False)
    component:   Mapped[Optional[str]] = mapped_column(String(50))
    details:     Mapped[dict] = mapped_column(JSONB, default=dict)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class RiskConfig(Base):
    __tablename__ = 'risk_config'

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scope:       Mapped[Optional[str]] = mapped_column(String(20))
    scope_id:    Mapped[Optional[str]] = mapped_column(String(36))
    param_name:  Mapped[str] = mapped_column(String(60), nullable=False)
    param_value: Mapped[str] = mapped_column(String(100), nullable=False)
    updated_by:  Mapped[Optional[str]] = mapped_column(ForeignKey('users.id'))
    updated_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# ML & BACKTESTS
# ===========================================================================
class MlModel(Base):
    __tablename__ = 'ml_models'

    id:             Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name:           Mapped[str] = mapped_column(String(100), nullable=False)
    version:        Mapped[str] = mapped_column(String(20), nullable=False)
    algorithm:      Mapped[Optional[str]] = mapped_column(String(50))
    features_json:  Mapped[dict] = mapped_column(JSONB, default=dict)
    metrics_json:   Mapped[dict] = mapped_column(JSONB, default=dict)
    status:         Mapped[str] = mapped_column(String(20), default='training')
    champion_since: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


class BacktestRun(Base):
    __tablename__ = 'backtest_runs'

    id:           Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    strategy_id:  Mapped[Optional[str]] = mapped_column(ForeignKey('strategies.id'))
    model_id:     Mapped[Optional[str]] = mapped_column(ForeignKey('ml_models.id'))
    from_date:    Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_date:      Mapped[datetime] = mapped_column(DateTime(timezone=True))
    config_json:  Mapped[dict] = mapped_column(JSONB, default=dict)
    results_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status:       Mapped[str] = mapped_column(String(20), default='pending')
    created_at:   Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())


# ===========================================================================
# AUDIT
# ===========================================================================
class AuditEvent(Base):
    __tablename__ = 'audit_events'

    id:          Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    event_type:  Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id:    Mapped[Optional[str]] = mapped_column(String(36))
    component:   Mapped[str] = mapped_column(String(50))
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id:   Mapped[Optional[str]] = mapped_column(String(36))
    details:     Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address:  Mapped[Optional[str]] = mapped_column(String(45))
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=utcnow())
