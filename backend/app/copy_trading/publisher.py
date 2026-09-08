"""
Copy-Trading Publisher — трансляция сделок в публичный Telegram-канал.
Публикует структурированные сообщения: вход, TP, SL, закрытие, P&L.
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class CopyTradeConfig:
    bot_token: str              # Telegram Bot API token
    channel_id: str             # @channel или -100...
    publish_entries: bool = True
    publish_exits: bool = True
    publish_sl_moves: bool = False
    include_pnl: bool = True
    min_win_rate_to_publish: float = 0.0  # 0 = публикуем все


class CopyTradingPublisher:
    """HTTP-пушер сообщений в Telegram."""

    def __init__(self, config: Optional[CopyTradeConfig] = None):
        self.config = config
        self._enabled = config is not None

    def configure(self, config: CopyTradeConfig) -> None:
        self.config = config
        self._enabled = True
        log.info("CopyTrading configured channel=%s", config.channel_id)

    async def on_entry(self, trade: dict) -> None:
        if not self._enabled or not self.config.publish_entries:
            return
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?").upper()
        entry = trade.get("entry_price", 0)
        tp = trade.get("tp")
        sl = trade.get("sl")
        lev = trade.get("leverage", 1)
        side_emoji = "🟢" if side == "LONG" else "🔴"

        msg = (
            f"{side_emoji} <b>НОВАЯ ПОЗИЦИЯ</b>\n"
            f"💰 <b>{symbol}</b> • {side} • {lev}x\n"
            f"👉 Вход: <code>{entry:.4f}</code>\n"
        )
        if tp:
            msg += f"✅ TP: <code>{tp:.4f}</code>\n"
        if sl:
            msg += f"❌ SL: <code>{sl:.4f}</code>\n"
        await self._send(msg)

    async def on_exit(self, trade: dict, pnl_pct: float,
                      pnl_usdt: float, outcome: str) -> None:
        if not self._enabled or not self.config.publish_exits:
            return
        symbol = trade.get("symbol", "?")
        side = trade.get("side", "?").upper()
        emoji = "💰" if pnl_pct >= 0 else "💸"
        outcome_label = {
            "win": "✅ ПРИБЫЛЬ", "loss": "❌ УБЫТОК",
            "partial": "🟡 ЧАСТИЧНО", "timeout": "⏰ ТАЙМАУТ"
        }.get(outcome, outcome.upper())

        msg = (
            f"{emoji} <b>ЗАКРЫТИЕ</b> {outcome_label}\n"
            f"💰 <b>{symbol}</b> {side}\n"
        )
        if self.config.include_pnl:
            sign = "+" if pnl_pct >= 0 else ""
            msg += f"P&L: <b>{sign}{pnl_pct:.2f}%</b> ({sign}{pnl_usdt:.2f} USDT)\n"

        await self._send(msg)

    async def on_sl_move(self, symbol: str, old_sl: float, new_sl: float) -> None:
        if not self._enabled or not self.config.publish_sl_moves:
            return
        msg = (f"🔄 SL передвинут {symbol}: "
               f"<code>{old_sl:.4f}</code> → <code>{new_sl:.4f}</code>")
        await self._send(msg)

    async def _send(self, text: str) -> None:
        try:
            import aiohttp
            url = (f"https://api.telegram.org/bot{self.config.bot_token}"
                   f"/sendMessage")
            async with aiohttp.ClientSession() as sess:
                await sess.post(url, json={
                    "chat_id": self.config.channel_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                })
        except Exception as e:
            log.error("CopyTrading send failed: %s", e)


copy_publisher = CopyTradingPublisher()
