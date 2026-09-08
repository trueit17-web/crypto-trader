"""Domain events flowing through Redis Streams."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Stream names
# ---------------------------------------------------------------------------
class Stream(str, Enum):
    RAW_MESSAGES     = 'stream:raw_messages'
    PARSED_SIGNALS   = 'stream:parsed_signals'
    VALIDATED_SIGNALS= 'stream:validated_signals'
    SCORED_SIGNALS   = 'stream:scored_signals'
    ORDERS           = 'stream:orders'
    FILLS            = 'stream:fills'
    RISK_EVENTS      = 'stream:risk_events'
    MARKET_DATA      = 'stream:market_data'
    ALERTS           = 'stream:alerts'


# ---------------------------------------------------------------------------
# Signal pipeline events
# ---------------------------------------------------------------------------
class SignalDecision(str, Enum):
    APPROVE      = 'APPROVE'
    REDUCE_SIZE  = 'REDUCE_SIZE'
    DELAY        = 'DELAY'
    PAPER_ONLY   = 'PAPER_ONLY'
    REJECT       = 'REJECT'
    PENDING      = 'PENDING'


@dataclass
class RawMessageEvent:
    id: str = field(default_factory=new_id)
    source_id: str = ''
    message_id: int = 0
    chat_id: int = 0
    text: str = ''
    edit_date: Optional[datetime] = None
    received_at: datetime = field(default_factory=utcnow)
    is_duplicate: bool = False


@dataclass
class ParsedSignalEvent:
    id: str = field(default_factory=new_id)
    raw_message_id: str = ''
    symbol: str = ''
    direction: str = ''   # long | short
    entry_min: Optional[Decimal] = None
    entry_max: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profits: list = field(default_factory=list)
    leverage: Optional[int] = None
    expiry_at: Optional[datetime] = None
    confidence: dict = field(default_factory=dict)
    parsed_at: datetime = field(default_factory=utcnow)


@dataclass
class ScoredSignalEvent:
    id: str = field(default_factory=new_id)
    parsed_signal_id: str = ''
    source_score: float = 0.0
    signal_score: float = 0.0
    final_score: float = 0.0
    decision: SignalDecision = SignalDecision.PENDING
    decision_reason: dict = field(default_factory=dict)
    size_fraction: float = 1.0
    created_at: datetime = field(default_factory=utcnow)


# ---------------------------------------------------------------------------
# Order events
# ---------------------------------------------------------------------------
class OrderStatus(str, Enum):
    OPEN             = 'open'
    FILLED           = 'filled'
    PARTIALLY_FILLED = 'partially_filled'
    CANCELLED        = 'cancelled'
    REJECTED         = 'rejected'


@dataclass
class OrderEvent:
    id: str = field(default_factory=new_id)
    client_order_id: str = ''
    exchange_order_id: str = ''
    exchange_id: str = ''
    symbol: str = ''
    side: str = ''       # buy | sell
    order_type: str = '' # market | limit | stop_market | stop_limit
    quantity: Decimal = Decimal(0)
    price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.OPEN
    source_type: str = '' # signal | strategy | manual
    source_id: str = ''
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class FillEvent:
    id: str = field(default_factory=new_id)
    order_id: str = ''
    fill_id: str = ''
    price: Decimal = Decimal(0)
    quantity: Decimal = Decimal(0)
    fee: Decimal = Decimal(0)
    fee_currency: str = 'USDT'
    timestamp_ms: int = 0
    is_maker: bool = False


# ---------------------------------------------------------------------------
# Risk events
# ---------------------------------------------------------------------------
class RiskSeverity(str, Enum):
    INFO     = 'info'
    WARNING  = 'warning'
    CRITICAL = 'critical'


@dataclass
class RiskEvent:
    id: str = field(default_factory=new_id)
    event_type: str = ''
    severity: RiskSeverity = RiskSeverity.INFO
    component: str = ''
    details: dict = field(default_factory=dict)
    is_resolved: bool = False
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class ReconciliationEvent:
    id: str = field(default_factory=new_id)
    exchange_id: str = ''
    discrepancy_type: str = ''  # position | order | balance
    local_value: Any = None
    exchange_value: Any = None
    created_at: datetime = field(default_factory=utcnow)
