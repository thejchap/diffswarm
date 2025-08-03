import asyncio
import logging
from dataclasses import dataclass, field
from typing import assert_never

from fastapi import WebSocket, WebSocketDisconnect
from pycrdt import (
    Array,
    Doc,
    YMessageType,
    YSyncMessageType,
    create_sync_message,  # pyright: ignore[reportUnknownVariableType]
    create_update_message,  # pyright: ignore[reportUnknownVariableType]
    handle_sync_message,  # pyright: ignore[reportUnknownVariableType]
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DiffDoc = Doc[Array[int]]


@dataclass
class YRoom:
    diff_id: str
    doc: DiffDoc
    clients: set[WebSocket] = field(default_factory=set)

    async def async_broadcast_updates(self) -> None:
        async with self.doc.events() as events:
            async for event in events:
                message = create_update_message(event.update)
                await self._broadcast_to_room(message)

    async def async_serve(self, client: WebSocket) -> None:
        self.clients.add(client)
        await client.accept()
        sync_msg = create_sync_message(self.doc)
        logger.info(
            "sending %(message_type)s to %(endpoint)s",
            {"message_type": YSyncMessageType.SYNC_STEP1.name, "endpoint": client.url},
        )
        await client.send_bytes(sync_msg)
        try:
            async for message in client.iter_bytes():
                if not message:
                    continue
                await self._async_handle_message(message, client)
        except Exception:
            logger.exception("bad")
        finally:
            self._disconnect(client)

    def _parse_message(
        self, message: bytes
    ) -> tuple[YMessageType, YSyncMessageType | None, bytes]:
        message_type = YMessageType(message[0])
        match message_type:
            case YMessageType.AWARENESS:
                return message_type, None, message[1:]
            case YMessageType.SYNC:
                sync_type = YSyncMessageType(message[1])
                return message_type, sync_type, message[1:]
        assert_never(message_type)

    async def _async_handle_message(
        self, raw_message: bytes, client: WebSocket
    ) -> None:
        message = self._parse_message(raw_message)
        match message:
            case YMessageType.AWARENESS, _, payload:
                logger.info(
                    "received %(message_type)s from %(endpoint)s",
                    {"message_type": message[0].name, "endpoint": client.url},
                )
                return
            case YMessageType.SYNC, sync_type, payload:
                logger.info(
                    "received %(message_type)s (%(sync_type)s) from %(endpoint)s",
                    {
                        "message_type": message[0].name,
                        "endpoint": client.url,
                        "sync_type": sync_type.name if sync_type is not None else None,
                    },
                )
                if reply := handle_sync_message(payload, self.doc):
                    await client.send_bytes(reply)
                return
        assert_never(message)

    def _disconnect(self, _client: WebSocket) -> None:
        pass

    async def _broadcast_to_room(
        self, message: bytes, exclude: WebSocket | None = None
    ) -> None:
        clients = self.clients.copy()
        for client in clients:
            if client == exclude:
                continue
            try:
                await client.send_bytes(message)
            except (WebSocketDisconnect, ConnectionResetError):
                logger.exception("broadast error")
            finally:
                self._disconnect(client)


class YWebSocketServer:
    def __init__(self) -> None:
        self.rooms: dict[str, YRoom] = {}

    async def async_serve(self, diff_id: str, client: WebSocket) -> None:
        doc = DiffDoc()
        room = self.rooms.setdefault(diff_id, YRoom(diff_id=diff_id, doc=doc))
        await asyncio.gather(room.async_serve(client), room.async_broadcast_updates())
