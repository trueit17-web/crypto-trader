"""
Webhook Receiver — входящие сигналы от TradingView, 3Commas, Pine Script.
EP: POST /api/v1/webhook/signal
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


# --- Примеры полезных пейлоадов ---
# TradingView Pine Alert:
# {"source":"tradingview","symbol":"BTCUSDT","side":"long",
#  "entry":{{close}},"tp":{{close}}*1.02,"sl":{{close}}*0.98,
#  "leverage":5,"size_pct":2,"secret":"YOUR_SECRET"}
#
# 3Commas webhook:
# {"message_type":"bot","bot_id":12345,"email_token":"...",
#  "delay_seconds":0,"pair":"USDT_BTC","action":"start_bot"}


class TVWebhookPayload(BaseModel):
    """TradingView / Pine Script format."""
    source: str = "tradingview"
    symbol: str
    side: str                       # long | short | close
    entry: Optional[float] = None
    tp: Optional[float] = None
    sl: Optional[float] = None
    leverage: float = 1.0
    size_pct: float = Field(default=1.0, ge=0.1, le=100.0)
    secret: Optional[str] = None   # опциональный секрет для верификации
    comment: Optional[str] = None

    @model_validator(mode="after")
    def normalize_symbol(self):
        self.symbol = self.symbol.upper().replace("/", "").replace("-", "")
        self.side = self.side.lower()
        return self


class ThreeCommasPayload(BaseModel):
    """3Commas bot webhook format."""
    message_type: str
    bot_id: Optional[int] = None
    email_token: Optional[str] = None
    pair: Optional[str] = None
    action: Optional[str] = None   # start_bot | stop_bot | panic_sell


class WebhookResponse(BaseModel):
    accepted: bool
    signal_id: Optional[str] = None
    message: str = ""


WEBHOOK_SECRET: Optional[str] = None   # загружается из config


def verify_tradingview_secret(payload_secret: Optional[str]) -> bool:
    if WEBHOOK_SECRET is None:
        return True   # секрет не настроен
    return payload_secret == WEBHOOK_SECRET


def verify_hmac_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 для вебхуков с X-Signature заголовком."""
    expected = hmac.new(
        secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.removeprefix("sha256="))


@router.post("/signal", response_model=WebhookResponse)
async def receive_signal(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """
    Универсальный webhook-ресивер.
    Автоматически распознаёт TradingView / 3Commas / произвольный формат.
    """
    body = await request.body()
    try:
        raw = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # HMAC верификация если есть заголовок
    if x_signature and WEBHOOK_SECRET:
        if not verify_hmac_signature(body, x_signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Распознаём формат
    if "message_type" in raw:    # 3Commas
        payload = ThreeCommasPayload(**raw)
        signal = _from_3commas(payload)
    else:                        # TradingView / custom
        payload = TVWebhookPayload(**raw)
        if not verify_tradingview_secret(payload.secret):
            raise HTTPException(status_code=401, detail="Wrong secret")
        signal = _from_tradingview(payload)

    if signal is None:
        return WebhookResponse(accepted=False, message="Ignored (close or unsupported)")

    # → передаём в signal pipeline
    signal_id = await _enqueue_signal(signal)
    log.info("Webhook ACCEPTED signal_id=%s source=%s %s %s",
             signal_id, signal["source"], signal["symbol"], signal["side"])
    return WebhookResponse(accepted=True, signal_id=signal_id,
                           message="Signal accepted")


def _from_tradingview(p: TVWebhookPayload) -> Optional[dict]:
    if p.side == "close":
        return None
    return {
        "source": p.source,
        "symbol": p.symbol,
        "side": p.side,
        "entry": p.entry,
        "tp": p.tp,
        "sl": p.sl,
        "leverage": p.leverage,
        "size_pct": p.size_pct,
        "comment": p.comment,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def _from_3commas(p: ThreeCommasPayload) -> Optional[dict]:
    if p.action not in ("start_bot", None):
        return None
    if not p.pair:
        return None
    symbol = p.pair.replace("USDT_", "") + "USDT"
    return {
        "source": f"3commas_bot_{p.bot_id}",
        "symbol": symbol,
        "side": "long",
        "entry": None, "tp": None, "sl": None,
        "leverage": 1.0, "size_pct": 1.0,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


async def _enqueue_signal(signal: dict) -> str:
    import uuid
    sid = str(uuid.uuid4())[:8]
    signal["signal_id"] = sid
    # TODO: передать в Redis queue или SignalRouter
    log.debug("Enqueue signal %s", signal)
    return sid
