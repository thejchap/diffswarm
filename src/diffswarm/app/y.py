import logging
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from pycrdt import (
    Array,
    Doc,  # pyright: ignore[reportUnknownVariableType]
    YMessageType,
    create_sync_message,  # pyright: ignore[reportUnknownVariableType]
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DiffDoc = Doc[Array[int]]


@dataclass
class YRoom:
    diff_id: str
    doc: DiffDoc
    clients: set[WebSocket] = field(default_factory=set)

    async def async_serve(self, client: WebSocket) -> None:
        self.clients.add(client)
        await client.accept()
        sync_msg = create_sync_message(self.doc)
        await client.send_bytes(sync_msg)
        try:
            async for message in client.iter_bytes():
                if not message:
                    continue
                logger.info(YMessageType(message[0]).name)
        except Exception:
            logger.exception("bad")
        finally:
            self._disconnect(client)

    def _disconnect(self, client: WebSocket) -> None:
        self.clients.discard(client)

    async def _broadcast_to_room(
        self, message: bytes, exclude: WebSocket | None = None
    ) -> None:
        for client in self.clients:
            if client == exclude:
                continue
            try:
                await client.send_bytes(message)
            except (WebSocketDisconnect, ConnectionResetError):
                logger.exception("broadast error")
            finally:
                self._disconnect(client)


class YWebSocketManager:
    def __init__(self) -> None:
        self.rooms: dict[str, YRoom] = {}

    async def async_serve(self, diff_id: str, client: WebSocket) -> None:
        doc = DiffDoc()
        room = self.rooms.setdefault(diff_id, YRoom(diff_id=diff_id, doc=doc))
        await room.async_serve(client)
