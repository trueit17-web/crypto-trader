"""
Multi-Account Manager — несколько суб-аккаунтов / бирж в одном интерфейсе.
Раздельные портфели, лимиты риска, API ключи на каждый аккаунт.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class AccountConfig:
    account_id: str             # уникальный идентификатор
    label: str                  # название ("Main", "Scalp", "Hedge")
    exchange: str               # binance | bybit | okx ...
    api_key: str
    api_secret: str
    api_passphrase: Optional[str] = None
    testnet: bool = False
    read_only: bool = False
    max_balance_pct: float = 100.0    # % от общего портфеля
    allowed_symbols: List[str] = field(default_factory=list)  # [] = все
    risk_per_trade_pct: float = 1.0
    max_open_positions: int = 10
    active: bool = True
    ip_whitelist: Optional[str] = None


@dataclass
class AccountState:
    account_id: str
    balance_usdt: float = 0.0
    open_positions: int = 0
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    status: str = "online"     # online | offline | error | rate_limited
    last_error: Optional[str] = None


class MultiAccountManager:
    """
    Центральный реестр аккаунтов.
    Каждый аккаунт → свой ExchangeAdapter.
    """

    def __init__(self):
        self._accounts: Dict[str, AccountConfig] = {}
        self._states: Dict[str, AccountState] = {}
        self._adapters: Dict[str, object] = {}  # account_id -> Exchange adapter

    def add_account(self, cfg: AccountConfig) -> None:
        """Registering a new trading account."""
        if cfg.account_id in self._accounts:
            log.warning("Account %s already registered, updating", cfg.account_id)
        self._accounts[cfg.account_id] = cfg
        self._states[cfg.account_id] = AccountState(account_id=cfg.account_id)
        log.info("Account added: %s [%s/%s] testnet=%s",
                 cfg.account_id, cfg.label, cfg.exchange, cfg.testnet)
        # TODO: инициализировать ExchangeAdapter

    def remove_account(self, account_id: str) -> bool:
        if account_id not in self._accounts:
            return False
        self._accounts.pop(account_id)
        self._states.pop(account_id, None)
        self._adapters.pop(account_id, None)
        log.info("Account removed: %s", account_id)
        return True

    def get_adapter(self, account_id: str) -> Optional[object]:
        return self._adapters.get(account_id)

    def list_accounts(self) -> List[dict]:
        result = []
        for acc_id, cfg in self._accounts.items():
            state = self._states.get(acc_id, AccountState(account_id=acc_id))
            result.append({
                "account_id": acc_id,
                "label": cfg.label,
                "exchange": cfg.exchange,
                "testnet": cfg.testnet,
                "active": cfg.active,
                "balance_usdt": state.balance_usdt,
                "open_positions": state.open_positions,
                "daily_pnl": state.daily_pnl,
                "status": state.status,
            })
        return result

    def update_state(self, account_id: str, **kwargs) -> None:
        state = self._states.get(account_id)
        if state:
            for k, v in kwargs.items():
                if hasattr(state, k):
                    setattr(state, k, v)

    def get_active_accounts(self) -> List[AccountConfig]:
        return [cfg for cfg in self._accounts.values() if cfg.active]

    def route_order(self, symbol: str,
                    strategy: Optional[str] = None) -> Optional[str]:
        """
        Определяет на какой аккаунт направить ордер.
        Логика: первый активный аккаунт с достаточным балансом.
        """
        for acc_id, cfg in self._accounts.items():
            if not cfg.active or cfg.read_only:
                continue
            if cfg.allowed_symbols and symbol not in cfg.allowed_symbols:
                continue
            state = self._states.get(acc_id)
            if state and state.open_positions >= cfg.max_open_positions:
                continue
            return acc_id
        return None

    def get_portfolio_summary(self) -> dict:
        """Агрегированное P&L и баланс по всем аккаунтам."""
        states = list(self._states.values())
        return {
            "total_accounts": len(states),
            "active_accounts": sum(1 for s in states if s.status == "online"),
            "total_balance_usdt": sum(s.balance_usdt for s in states),
            "total_open_positions": sum(s.open_positions for s in states),
            "total_daily_pnl": sum(s.daily_pnl for s in states),
            "total_pnl": sum(s.total_pnl for s in states),
        }


multi_account_manager = MultiAccountManager()
