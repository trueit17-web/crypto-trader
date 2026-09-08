#!/bin/bash
# =============================================================
# CryptoTrader — One-Command Installer
# Поддерживаемые ОС: Ubuntu 20.04 / 22.04 / 24.04, Debian 11/12
# Запуск: bash install.sh
# =============================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()  { echo -e "${GREEN}✅ $1${NC}"; }
info(){ echo -e "${YELLOW}➤  $1${NC}"; }
err(){ echo -e "${RED}❌ $1${NC}"; exit 1; }

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_NAME="cryptotrader"
DB_USER="postgres"
DB_PASS="postgres"
DB_SYNC_URL="postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}"
DB_ASYNC_URL="postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}"

info "CryptoTrader installer | Project: $PROJECT_DIR"

# ── 1. Системные пакеты ─────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    postgresql postgresql-client \
    redis-server \
    git curl build-essential libpq-dev > /dev/null
ok "System packages installed"

# ── 2. Выбираем Python ──────────────────────────────────────
PYTHON=""
for PY in python3.12 python3.11 python3.10 python3; do
    if command -v "$PY" &>/dev/null; then PYTHON="$PY"; break; fi
done
[ -z "$PYTHON" ] && err "Python 3 not found"
ok "Python: $PYTHON ($($PYTHON --version))"

# ── 3. PostgreSQL ────────────────────────────────────────────
info "Setting up PostgreSQL..."
service postgresql start
su - postgres -c "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\"" \
    | grep -q 1 || su - postgres -c "createdb ${DB_NAME}"
su - postgres -c "psql -c \"ALTER USER ${DB_USER} PASSWORD '${DB_PASS}';\"" > /dev/null 2>&1
ok "PostgreSQL: db=${DB_NAME} user=${DB_USER} pass=${DB_PASS}"

# ── 4. Redis ─────────────────────────────────────────────────
info "Starting Redis..."
service redis-server start 2>/dev/null || service redis start 2>/dev/null
ok "Redis started"

# ── 5. Python venv ───────────────────────────────────────────
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

# ── 6. .env ──────────────────────────────────────────────────
if [ ! -f "$PROJECT_DIR/.env" ]; then
    info "Creating .env..."
    JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(64))')
    cat > "$PROJECT_DIR/.env" << EOF
DATABASE_URL=${DB_ASYNC_URL}
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
DEBUG=false
ENVIRONMENT=production
EOF
    ok ".env created"
else
    ok ".env already exists — skipping"
fi

# ── 7. alembic.ini — принудительно выставляем правильный URL ─
info "Updating alembic.ini..."
ALEMBIC_INI="$PROJECT_DIR/backend/alembic.ini"
# Убеждаемся что script_location есть
grep -q '^script_location' "$ALEMBIC_INI" 2>/dev/null || \
    sed -i '1s|^|[alembic]\nscript_location = migrations\n|' "$ALEMBIC_INI"
# Выставляем синхронный URL
if grep -q '^sqlalchemy.url' "$ALEMBIC_INI"; then
    sed -i "s|^sqlalchemy.url.*|sqlalchemy.url = ${DB_SYNC_URL}|" "$ALEMBIC_INI"
else
    echo "sqlalchemy.url = ${DB_SYNC_URL}" >> "$ALEMBIC_INI"
fi
ok "alembic.ini updated"

# ── 8. Миграции ──────────────────────────────────────────────
info "Running database migrations..."
cd "$PROJECT_DIR/backend"
# Создаём первую миграцию если папка versions пустая
if [ -z "$(ls migrations/versions/ 2>/dev/null)" ]; then
    PYTHONPATH="$PROJECT_DIR/backend" \
        "$PROJECT_DIR/venv/bin/alembic" -c alembic.ini \
        revision --autogenerate -m "initial" > /dev/null 2>&1 || true
fi
PYTHONPATH="$PROJECT_DIR/backend" \
    "$PROJECT_DIR/venv/bin/alembic" -c alembic.ini upgrade head
ok "Migrations applied"

# ── 9. systemd service ───────────────────────────────────────
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

# ── Done ─────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${GREEN}═══════════════════════════════${NC}"
echo -e "${GREEN}  CryptoTrader установлен!${NC}"
echo -e "${GREEN}═══════════════════════════════${NC}"
echo ""
echo "  API:  http://${SERVER_IP}:8000"
echo "  Docs: http://${SERVER_IP}:8000/docs"
echo ""
echo "  make status   — статус сервиса"
echo "  make logs      — логи в реальном времени"
echo "  make restart   — перезапуск"
echo ""
