# CryptoTrader

Автоматический крипто трейдинг бот с ML-регулированием сигналов.

## Требования

- **ОС:** Ubuntu 22.04 LTS
- **ОЗУ:** 2 GB+ RAM, 20 GB+ SSD
- **Права:** root или sudo

## Установка — 3 команды

```bash
# 1. Клонировать репозиторий
git clone https://github.com/YOUR_USERNAME/crypto-trader.git
cd crypto-trader

# 2. Запустить инсталлятор
bash install.sh

# 3. Готово! API доступен на:
# http://YOUR_IP:8000
# http://YOUR_IP:8000/docs
```

## Команды

| Команда | Действие |
|---------|----------|
| `make start` | Запустить API |
| `make stop` | Остановить API |
| `make restart` | Перезапустить API |
| `make logs` | Смотреть логи |
| `make status` | Статус сервиса |
| `make migrate` | Применить миграции |
| `make update` | Git pull + миграции + рестарт |
| `make dev` | Dev-режим с auto-reload |
| `make test` | Запустить тесты |

## Архитектура

```
crypto-trader/
├── install.sh        ← однокомандный инсталлятор
├── Makefile          ← управление проектом
├── .env              ← ваши конфиги (auto-generated)
├── backend/
│   ├── app/
│   │   ├── order/       trailing_stop, partial_close
│   │   ├── strategy/    pyramiding, dca
│   │   ├── risk/        engine, auto_hedge
│   │   ├── ml/          champion_challenger, outcome_tracker
│   │   ├── signal/      parser, scorer, leaderboard
│   │   ├── analytics/   pattern_analyzer
│   │   ├── backtest/    engine, walk_forward
│   │   ├── webhook/     receiver (TradingView, 3Commas)
│   │   ├── copy_trading/ publisher (Telegram)
│   │   └── multi_account/ manager
│   ├── migrations/
│   └── requirements.txt
├── frontend/
│   ├── public/  manifest.json, sw.js (PWA)
│   └── src/pages/ Dashboard, Positions, Signals, Leaderboard...
└── infra/
    └── docker-compose.yml
```

## Настройка `.env`

Файл `.env` автоматически создаётся при `bash install.sh`. Значения по умолчанию:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost/cryptotrader
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=<авто-генерируется>
```
