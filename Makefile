.PHONY: install start stop restart logs status migrate shell test update

PROJECT_DIR := $(shell pwd)
PYTHON := $(PROJECT_DIR)/venv/bin/python
PIP := $(PROJECT_DIR)/venv/bin/pip
ALEMBIC := PYTHONPATH=$(PROJECT_DIR)/backend $(PROJECT_DIR)/venv/bin/alembic -c $(PROJECT_DIR)/backend/alembic.ini
UVICORN := $(PROJECT_DIR)/venv/bin/uvicorn

## ── Установка ────────────────────────────────────
install:  ## Полная установка (bash install.sh)
	@bash install.sh

## ── Сервис ──────────────────────────────────────
start:    ## Запустить API
	@systemctl start cryptotrader
	@echo "✅ Started"

stop:     ## Остановить API
	@systemctl stop cryptotrader
	@echo "✅ Stopped"

restart:  ## Перезапустить API
	@systemctl restart cryptotrader
	@echo "✅ Restarted"

logs:     ## Смотреть логи в реальном времени
	@journalctl -u cryptotrader -f

status:   ## Статус сервиса
	@systemctl status cryptotrader

## ── БД ─────────────────────────────────────────
migrate:  ## Применить миграции
	@cd backend && $(ALEMBIC) upgrade head

migrate-create:  ## Создать новую миграцию (make migrate-create MSG="add table")
	@cd backend && $(ALEMBIC) revision --autogenerate -m "$(MSG)"

db-shell:  ## Открыть psql
	@su - postgres -c "psql cryptotrader"

## ── Разработка ─────────────────────────────────
dev:      ## Запустить в dev-режиме (с auto-reload)
	@cd backend && PYTHONPATH=$(PROJECT_DIR)/backend \
	  $(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

shell:    ## Python шелл с контекстом проекта
	@PYTHONPATH=$(PROJECT_DIR)/backend $(PYTHON) -i -c \
	  "from app.core.database import *; from app.core.models import *; print('Context loaded')"

test:     ## Запустить тесты
	@PYTHONPATH=$(PROJECT_DIR)/backend \
	  $(PROJECT_DIR)/venv/bin/pytest backend/tests/ -v

## ── Обновление ───────────────────────────────
update:   ## Пулл + миграции + рестарт
	@git pull
	@$(PIP) install -q -r backend/requirements.txt
	@cd backend && $(ALEMBIC) upgrade head
	@systemctl restart cryptotrader
	@echo "✅ Updated and restarted"

help:     ## Показать все команды
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
