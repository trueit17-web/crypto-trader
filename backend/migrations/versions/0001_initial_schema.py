"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgcrypto есть в стандартном PostgreSQL, timescaledb — нет (убрано)
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('totp_secret', sa.String(64)),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- exchanges ---
    op.create_table(
        'exchanges',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True),
        sa.Column('adapter_class', sa.String(100), nullable=False),
        sa.Column('config_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    op.create_table(
        'exchange_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False),
        sa.Column('encrypted_api_key', sa.Text(), nullable=False),
        sa.Column('encrypted_secret', sa.Text(), nullable=False),
        sa.Column('permissions_verified', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- instruments ---
    op.create_table(
        'instruments',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_normalized', sa.String(30), nullable=False),
        sa.Column('symbol_native', sa.String(30), nullable=False),
        sa.Column('market_type', sa.String(20), nullable=False),
        sa.Column('tick_size', sa.Numeric(20, 10)),
        sa.Column('lot_size', sa.Numeric(20, 10)),
        sa.Column('min_notional', sa.Numeric(20, 4)),
        sa.Column('max_leverage', sa.Integer(), server_default='1'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )
    op.create_unique_constraint('uq_instrument_exchange_symbol_type', 'instruments', ['exchange_id', 'symbol_normalized', 'market_type'])

    # --- candles (обычная таблица, без timescaledb) ---
    op.create_table(
        'candles',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exchange_id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('timeframe', sa.String(5), nullable=False),
        sa.Column('open',  sa.Numeric(24, 8), nullable=False),
        sa.Column('high',  sa.Numeric(24, 8), nullable=False),
        sa.Column('low',   sa.Numeric(24, 8), nullable=False),
        sa.Column('close', sa.Numeric(24, 8), nullable=False),
        sa.Column('volume', sa.Numeric(30, 8), nullable=False),
        sa.Column('quote_volume', sa.Numeric(30, 8), nullable=False),
        sa.PrimaryKeyConstraint('time', 'exchange_id', 'symbol', 'timeframe'),
    )
    op.create_index('ix_candles_time', 'candles', ['time'])
    op.create_index('ix_candles_symbol_timeframe', 'candles', ['symbol', 'timeframe'])

    # --- funding_rates (обычная таблица, без timescaledb) ---
    op.create_table(
        'funding_rates',
        sa.Column('time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exchange_id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('rate', sa.Numeric(20, 10), nullable=False),
        sa.PrimaryKeyConstraint('time', 'exchange_id', 'symbol'),
    )
    op.create_index('ix_funding_rates_time', 'funding_rates', ['time'])

    # --- telegram_sources ---
    op.create_table(
        'telegram_sources',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('channel_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('is_authorized', sa.Boolean(), server_default='false'),
        sa.Column('is_paper_only', sa.Boolean(), server_default='true'),
        sa.Column('quality_score', sa.Numeric(4, 3), server_default='0.500'),
        sa.Column('signal_count', sa.Integer(), server_default='0'),
        sa.Column('win_rate', sa.Numeric(4, 3), server_default='0.000'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- raw_messages ---
    op.create_table(
        'raw_messages',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('telegram_sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('message_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('text', sa.Text(), server_default=''),
        sa.Column('edit_date', sa.DateTime(timezone=True)),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
        sa.Column('is_processed', sa.Boolean(), server_default='false'),
        sa.Column('is_duplicate', sa.Boolean(), server_default='false'),
    )
    op.create_unique_constraint('uq_raw_message_source_msgid', 'raw_messages', ['source_id', 'message_id'])
    op.create_index('ix_raw_messages_received_at', 'raw_messages', ['received_at'])

    # --- parsed_signals ---
    op.create_table(
        'parsed_signals',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('raw_message_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('raw_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('entry_min', sa.Numeric(24, 8)),
        sa.Column('entry_max', sa.Numeric(24, 8)),
        sa.Column('stop_loss', sa.Numeric(24, 8)),
        sa.Column('take_profits', postgresql.JSONB(), server_default='[]'),
        sa.Column('leverage', sa.Integer()),
        sa.Column('expiry_at', sa.DateTime(timezone=True)),
        sa.Column('confidence', postgresql.JSONB(), server_default='{}'),
        sa.Column('parsed_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- signal_scores ---
    op.create_table(
        'signal_scores',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('parsed_signal_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('parsed_signals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('signal_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('final_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),
        sa.Column('decision_reason', postgresql.JSONB(), server_default='{}'),
        sa.Column('size_fraction', sa.Numeric(4, 3), server_default='1.000'),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- strategies ---
    op.create_table(
        'strategies',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('class_name', sa.String(100), nullable=False),
        sa.Column('config_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('is_active', sa.Boolean(), server_default='false'),
        sa.Column('mode', sa.String(20), server_default='paper'),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- orders ---
    op.create_table(
        'orders',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('client_order_id', sa.String(64), nullable=False, unique=True),
        sa.Column('exchange_order_id', sa.String(64)),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id'), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('side', sa.String(5), nullable=False),
        sa.Column('order_type', sa.String(20), nullable=False),
        sa.Column('quantity', sa.Numeric(24, 8), nullable=False),
        sa.Column('price', sa.Numeric(24, 8)),
        sa.Column('status', sa.String(20), server_default='open'),
        sa.Column('source_type', sa.String(20), server_default='manual'),
        sa.Column('source_id', sa.String(36)),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('strategies.id')),
        sa.Column('signal_decision_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('signal_scores.id')),
        sa.Column('idempotency_key', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )
    op.create_index('ix_orders_status', 'orders', ['status'])
    op.create_index('ix_orders_exchange_id', 'orders', ['exchange_id'])

    # --- fills ---
    op.create_table(
        'fills',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fill_id', sa.String(64), nullable=False),
        sa.Column('price', sa.Numeric(24, 8), nullable=False),
        sa.Column('quantity', sa.Numeric(24, 8), nullable=False),
        sa.Column('fee', sa.Numeric(20, 8), server_default='0'),
        sa.Column('fee_currency', sa.String(10), server_default='USDT'),
        sa.Column('timestamp_ms', sa.BigInteger()),
        sa.Column('is_maker', sa.Boolean(), server_default='false'),
    )

    # --- positions ---
    op.create_table(
        'positions',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id'), nullable=False),
        sa.Column('symbol', sa.String(30), nullable=False),
        sa.Column('side', sa.String(5), nullable=False),
        sa.Column('quantity', sa.Numeric(24, 8), nullable=False),
        sa.Column('entry_price', sa.Numeric(24, 8), nullable=False),
        sa.Column('margin_mode', sa.String(10), server_default='isolated'),
        sa.Column('leverage', sa.Integer(), server_default='1'),
        sa.Column('unrealized_pnl', sa.Numeric(20, 4), server_default='0'),
        sa.Column('liquidation_price', sa.Numeric(24, 8)),
        sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- balances ---
    op.create_table(
        'balances',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('exchange_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('exchanges.id'), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('total', sa.Numeric(24, 8), server_default='0'),
        sa.Column('available', sa.Numeric(24, 8), server_default='0'),
        sa.Column('locked', sa.Numeric(24, 8), server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )
    op.create_unique_constraint('uq_balance_exchange_currency', 'balances', ['exchange_id', 'currency'])

    # --- portfolio_snapshots ---
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
        sa.Column('total_equity', sa.Numeric(24, 4), nullable=False),
        sa.Column('unrealized_pnl', sa.Numeric(20, 4), server_default='0'),
        sa.Column('realized_pnl_day', sa.Numeric(20, 4), server_default='0'),
        sa.Column('nav_json', postgresql.JSONB(), server_default='{}'),
    )

    # --- risk_events ---
    op.create_table(
        'risk_events',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('component', sa.String(50)),
        sa.Column('details', postgresql.JSONB(), server_default='{}'),
        sa.Column('is_resolved', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- risk_config ---
    op.create_table(
        'risk_config',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('scope', sa.String(20)),
        sa.Column('scope_id', sa.String(36)),
        sa.Column('param_name', sa.String(60), nullable=False),
        sa.Column('param_value', sa.String(100), nullable=False),
        sa.Column('updated_by', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- ml_models ---
    op.create_table(
        'ml_models',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('algorithm', sa.String(50)),
        sa.Column('features_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('metrics_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('status', sa.String(20), server_default='training'),
        sa.Column('champion_since', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- backtest_runs ---
    op.create_table(
        'backtest_runs',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('strategies.id')),
        sa.Column('model_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('ml_models.id')),
        sa.Column('from_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('to_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('config_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('results_json', postgresql.JSONB(), server_default='{}'),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )

    # --- audit_events (append-only) ---
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('event_type', sa.String(60), nullable=False),
        sa.Column('actor_id', sa.String(36)),
        sa.Column('component', sa.String(50)),
        sa.Column('entity_type', sa.String(50)),
        sa.Column('entity_id', sa.String(36)),
        sa.Column('details', postgresql.JSONB(), server_default='{}'),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )
    op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'], postgresql_using='brin')
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: UPDATE/DELETE not allowed';
        END;
        $$;

        CREATE TRIGGER trg_audit_immutable
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)

    # --- sessions ---
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('refresh_token_hash', sa.String(128), nullable=False),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )

    # --- api_keys ---
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=False), server_default=sa.text('gen_random_uuid()'), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(128), nullable=False),
        sa.Column('permissions', postgresql.JSONB(), server_default='[]'),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("timezone('UTC', now())")),
    )


def downgrade() -> None:
    for table in [
        'api_keys', 'sessions', 'audit_events', 'backtest_runs', 'ml_models',
        'risk_config', 'risk_events', 'portfolio_snapshots', 'balances',
        'positions', 'fills', 'orders', 'strategies', 'signal_scores',
        'parsed_signals', 'raw_messages', 'telegram_sources',
        'funding_rates', 'candles', 'instruments',
        'exchange_credentials', 'exchanges', 'users',
    ]:
        op.drop_table(table)
