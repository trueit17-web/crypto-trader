# CryptoTrader Platform

Платформа алгоритмической и сигнальной криптовалютной торговли.

> ⚠️ **Предупреждение:** Это программное обеспечение предназначено исключительно для команды разработчиков. Криптовалютная торговля сопряжена с высоким риском потери капитала. Никакая система не гарантирует прибыльность. Не используйте реальный капитал без многомесячного тестирования и независимого аудита.

---

## Архитектура

```
Frontend (React + TypeScript)
    ↓ REST API + WebSocket
Backend (FastAPI / Python)
    ↓ Redis Streams
Exchange Adapters | Signal Pipeline | Risk Engine | Order Management
    ↓
PostgreSQL (TimescaleDB) + Redis
    ↓
Binance | Bybit | KuCoin | OKX | BingX | Bitget | BitMEX | HyperLiquid
```

## Быстрый старт (Dev)

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd crypto-trader

# 2. Настроить переменные окружения
cp .env.example .env
# Отредактировать .env — заполнить DB пароли, JWT секрет

# 3. Запустить инфраструктуру
cd infra
docker compose up -d postgres redis

# 4. Установить зависимости backend
cd ../backend
pip install -r requirements.txt

# 5. Применить миграции БД
alembic upgrade head

# 6. Запустить backend
uvicorn app.main:app --reload

# Или запустить всё через Docker Compose
cd ../infra
docker compose up
```

## Структура проекта

```
crypto-trader/
├── backend/
│   ├── app/
│   │   ├── core/           # Конфиг, БД, Redis, события
│   │   ├── auth/           # JWT, TOTP, RBAC
│   │   ├── exchange/       # Адаптеры бирж (Binance, Bybit, ...)
│   │   ├── signal/         # Парсер, валидатор, скорер сигналов
│   │   ├── strategy/       # Базовый класс + EMA Crossover стратегия
│   │   ├── risk/           # Risk Engine с hard limits
│   │   ├── backtest/       # Backtesting без look-ahead
│   │   ├── order/          # OMS, idempotent execution
│   │   ├── portfolio/      # Учёт позиций и баланса
│   │   ├── telegram/       # Telegram ingestion
│   │   ├── ml/             # ML registry, champion-challenger
│   │   ├── notification/   # Уведомления
│   │   ├── audit/          # Append-only audit log
│   │   └── api/v1/         # FastAPI routers
│   ├── migrations/         # Alembic миграции
│   ├── tests/
│   │   ├── unit/           # Юнит тесты (>80% coverage цель)
│   │   └── integration/    # Интеграционные тесты
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/               # React + TypeScript dashboard
├── infra/
│   ├── docker-compose.yml  # Полный стек: PG, Redis, Backend, Frontend, Grafana
│   ├── prometheus/
│   └── grafana/
├── .env.example
├── .pre-commit-config.yaml
└── .github/workflows/ci.yml
```

## Тикеты (план реализации)

| Тикет | Описание | Приоритет | Статус |
|-------|----------|-----------|--------|
| TICK-001 | Инициализация репозитория и dev environment | P0 | ✅ Done |
| TICK-002 | Core domain модели и миграции БД | P0 | ✅ Done |
| TICK-003 | Аутентификация и RBAC | P0 | ✅ Done |
| TICK-004 | Exchange adapter — базовый интерфейс | P0 | ✅ Done |
| TICK-005 | Binance adapter (полный) | P1 | ✅ Done |
| TICK-006 | Bybit adapter (полный) | P1 | ✅ Done |
| TICK-007 | Market data ingestion | P1 | 🔄 Next |
| TICK-008 | Risk engine — hard limits | P1 | ✅ Done |
| TICK-009 | Paper trading и OMS | P1 | 🔄 Next |
| TICK-010 | Telegram ingestion и базовый парсер | P2 | ✅ Done |

## Тесты

```bash
cd backend
pytest tests/ -v --cov=app
```

## Безопасность

- Все секреты через `.env` (никогда не в git)
- В production: HashiCorp Vault или AWS Secrets Manager
- API ключи бирж БЕЗ прав вывода средств
- MFA обязательна для ролей Trader и Admin
- Audit log защищён от изменений (append-only триггер в PostgreSQL)

## Роли (RBAC)

| Роль | Просмотр | Ручное одобрение | Kill Switch | Настройка |
|------|----------|-----------------|-------------|----------|
| viewer | ✅ | ❌ | ❌ | ❌ |
| analyst | ✅ | ❌ | ❌ | ❌ |
| trader | ✅ | ✅ | ❌ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ |
