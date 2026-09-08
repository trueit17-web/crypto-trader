#!/bin/bash
# =============================================================
# CryptoTrader — One-Command Installer
# Поддерживаемые ОС: Ubuntu 20.04 / 22.04 / 24.04, Debian 11/12
# Запуск: bash install.sh
# =============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()  { echo -e "${GREEN}\u2705 $1${NC}"; }
info(){ echo -e "${YELLOW}\u27a4  $1${NC}"; }
err(){ echo -e "${RED}\u274c $1${NC}"; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
info "CryptoTrader installer started"
info "Project dir: $PROJECT_DIR"

# ---- 1. Системные пакеты ----
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    postgresql postgresql-client \
    redis-server \
    git curl build-essential libpq-dev \
    software-properties-common > /dev/null
ok "Base packages installed"

# ---- 2. Выбираем Python (3.11 предпочтительно, fallback на доступный) ----
PYTHON=""
for PY in python3.11 python3.12 python3.10 python3.9 python3; do
    if command -v "$PY" &>/dev/null; then
        PYTHON="$PY"
        break
    fi
done

# Если python3.11 не нашли — устанавливаем через deadsnakes PPA
if [ "$PYTHON" = "python3" ] || [ -z "$PYTHON" ]; then
    PY_VER=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [ "$PY_VER" -lt 10 ]; then
        info "Python < 3.10 detected, installing 3.11 via deadsnakes PPA..."
        add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1
        apt-get update -qq
        apt-get install -y -qq python3.11 python3.11-venv python3.11-distutils > /dev/null
        PYTHON="python3.11"
    fi
fi

[ -z "$PYTHON" ] && err "Python 3 not found!"
ok "Using Python: $PYTHON ($("$PYTHON" --version))"

# ---- 3. PostgreSQL ----
info "Setting up PostgreSQL..."
service postgresql start || pg_ctlcluster $(pg_lsclusters -h | awk '{print $1}' | head -1) main start

su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='cryptotrader'\"" \
  | grep -q 1 || su - postgres -c "createdb cryptotrader"
su - postgres -c "psql -c \"ALTER USER postgres PASSWORD 'postgres';\"" > /dev/null 2>&1
ok "PostgreSQL ready  (db=cryptotrader  user=postgres  pass=postgres)"

# ---- 4. Redis ----
info "Starting Redis..."
service redis-server start || service redis start
ok "Redis ready"

# ---- 5. Python venv ----
info "Creating Python venv..."
cd "$PROJECT_DIR"
"$PYTHON" -m venv venv
venv/bin/pip install --upgrade pip -q
venv/bin/pip install -q \
    fastapi "uvicorn[standard]" \
    "sqlalchemy[asyncio]" alembic \
    asyncpg psycopg2-binary \
    redis pydantic pydantic-settings \
    "python-jose[cryptography]" "passlib[bcrypt]" \
    python-multipart aiohttp aiofiles \
    python-dotenv httpx
ok "Python dependencies installed"

# ---- 6. .env ----
if [ ! -f "$PROJECT_DIR/.env" ]; then
    info "Creating .env..."
    JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(64))')
    cat > "$PROJECT_DIR/.env" << EOF
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/cryptotrader
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
DEBUG=false
ENVIRONMENT=production
EOF
    ok ".env created with random JWT secret"
else
    ok ".env already exists, skipping"
fi

# ---- 7. Sync migrations/env.py ----
info "Patching migrations/env.py..."
mkdir -p "$PROJECT_DIR/backend/migrations"
cat > "$PROJECT_DIR/backend/migrations/env.py" << 'PYEOF'
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

try:
    from app.core.models import Base
    target_metadata = Base.metadata
except ImportError:
    target_metadata = None

try:
    from app.core.config import settings
    url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", url)
except Exception:
    pass

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
PYEOF
ok "migrations/env.py patched"

# ---- 8. alembic.ini URL ----
PG_SYNC_URL="postgresql://postgres:postgres@localhost/cryptotrader"
if grep -q "^sqlalchemy.url" "$PROJECT_DIR/backend/alembic.ini" 2>/dev/null; then
    sed -i "s|^sqlalchemy.url.*|sqlalchemy.url = ${PG_SYNC_URL}|" "$PROJECT_DIR/backend/alembic.ini"
else
    echo "sqlalchemy.url = ${PG_SYNC_URL}" >> "$PROJECT_DIR/backend/alembic.ini"
fi
ok "alembic.ini updated"

# ---- 9. Миграции ----
info "Running database migrations..."
cd "$PROJECT_DIR/backend"
PYTHONPATH="$PROJECT_DIR/backend" \
    "$PROJECT_DIR/venv/bin/alembic" revision --autogenerate -m "initial" > /dev/null 2>&1 || true
PYTHONPATH="$PROJECT_DIR/backend" \
    "$PROJECT_DIR/venv/bin/alembic" upgrade head
ok "Migrations applied"

# ---- 10. systemd ----
info "Creating systemd service..."
cat > /etc/systemd/system/cryptotrader.service << EOF
[Unit]
Description=CryptoTrader API
After=network.target postgresql.service redis-server.service

[Service]
User=root
WorkingDirectory=${PROJECT_DIR}/backend
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cryptotrader
systemctl start cryptotrader
ok "systemd service started"

# ---- Done ----
echo ""
echo -e "${GREEN}═════════════════════════════════${NC}"
echo -e "${GREEN}  CryptoTrader установлен!${NC}"
echo -e "${GREEN}═════════════════════════════════${NC}"
echo ""
echo "  API:  http://$(hostname -I | awk '{print $1}'):8000"
echo "  Docs: http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
echo "  Статус: systemctl status cryptotrader"
echo "  Логи:   make logs"
echo ""
