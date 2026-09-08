"""Telegram message ingestion service (TICK-010)."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.events import RawMessageEvent, Stream
from app.core.redis_client import queue

logger = logging.getLogger(__name__)


class TelegramIngestionService:
    """
    Listens to authorised Telegram channels/groups,
    deduplicates messages, and emits RawMessageEvent to Redis Streams.

    Requires: pyrogram client (or telethon) pre-configured with session string.
    """

    def __init__(self, authorized_channels: dict[int, str]):
        """
        authorized_channels: {channel_id: source_id (UUID in DB)}
        """
        self._channels = authorized_channels
        self._seen: set[str] = set()  # dedup cache: f"{source_id}:{message_id}"
        self._client = None

    async def start(self) -> None:
        """Start listening. Call from background task."""
        try:
            from pyrogram import Client, filters
            from pyrogram.types import Message
            from app.core.config import settings

            self._client = Client(
                'crypto_trader_session',
                api_id=settings.TELEGRAM_API_ID,
                api_hash=settings.TELEGRAM_API_HASH,
                session_string=settings.TELEGRAM_SESSION_STRING,
                in_memory=True,
            )

            @self._client.on_message(
                filters.chat(list(self._channels.keys()))
            )
            async def on_message(client, message: Message):
                await self._handle_message(message)

            @self._client.on_edited_message(
                filters.chat(list(self._channels.keys()))
            )
            async def on_edit(client, message: Message):
                await self._handle_message(message, is_edit=True)

            await self._client.start()
            logger.info('Telegram ingestion started, watching %d channels', len(self._channels))
            await asyncio.gather(asyncio.get_event_loop().create_future())  # run forever

        except ImportError:
            logger.warning('pyrogram not installed — Telegram ingestion disabled')

    async def _handle_message(self, message, is_edit: bool = False) -> None:
        channel_id = message.chat.id
        source_id = self._channels.get(channel_id)
        if not source_id:
            return

        dedup_key = f'{source_id}:{message.id}'
        is_duplicate = dedup_key in self._seen
        if not is_duplicate:
            self._seen.add(dedup_key)

        event = RawMessageEvent(
            source_id=source_id,
            message_id=message.id,
            chat_id=channel_id,
            text=message.text or message.caption or '',
            edit_date=datetime.fromtimestamp(message.edit_date, tz=timezone.utc) if message.edit_date else None,
            received_at=datetime.now(timezone.utc),
            is_duplicate=is_duplicate,
        )

        # Publish to Redis Stream
        r = queue()
        import json, dataclasses
        data = {
            k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
            for k, v in dataclasses.asdict(event).items()
        }
        await r.xadd(Stream.RAW_MESSAGES.value, data)
        logger.debug('Ingested message %d from channel %d (duplicate=%s)', message.id, channel_id, is_duplicate)

    async def stop(self) -> None:
        if self._client:
            await self._client.stop()
            logger.info('Telegram ingestion stopped')
