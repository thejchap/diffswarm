import asyncio
import contextlib
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
        try:
            self.clients.add(client)
            await client.accept()
            sync_msg = create_sync_message(self.doc)
            logger.info(
                "sending %(message_type)s to %(endpoint)s",
                {
                    "message_type": YSyncMessageType.SYNC_STEP1.name,
                    "endpoint": client.url,
                },
            )
            await client.send_bytes(sync_msg)

            async for message in client.iter_bytes():
                if not message:
                    continue
                await self._async_handle_message(message, client)

        except WebSocketDisconnect:
            logger.info("client disconnected normally: %s", client.url)
        except ConnectionResetError:
            logger.warning("client connection reset: %s", client.url)
        except Exception:
            logger.exception("unexpected error serving client %s", client.url)
        finally:
            self._disconnect(client)

    def _parse_message(
        self, message: bytes
    ) -> tuple[YMessageType, YSyncMessageType | None, bytes]:
        if len(message) == 0:
            msg = "empty message received"
            raise ValueError(msg)

        try:
            message_type = YMessageType(message[0])
        except ValueError as e:
            msg = f"invalid message type: {message[0]}"
            raise ValueError(msg) from e

        match message_type:
            case YMessageType.AWARENESS:
                return message_type, None, message[1:]
            case YMessageType.SYNC:
                min_sync_message_length = 2
                if len(message) < min_sync_message_length:
                    msg = "sync message too short"
                    raise ValueError(msg)
                try:
                    sync_type = YSyncMessageType(message[1])
                except ValueError as e:
                    msg = f"invalid sync type: {message[1]}"
                    raise ValueError(msg) from e
                return message_type, sync_type, message[1:]
        assert_never(message_type)

    async def _async_handle_message(
        self, raw_message: bytes, client: WebSocket
    ) -> None:
        try:
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
                            "sync_type": sync_type.name
                            if sync_type is not None
                            else None,
                        },
                    )
                    try:
                        if reply := handle_sync_message(payload, self.doc):
                            await client.send_bytes(reply)
                    except Exception:
                        logger.exception(
                            "error handling sync message from %s", client.url
                        )
                    return
            assert_never(message)
        except ValueError as e:
            logger.warning("invalid message from client %s: %s", client.url, e)
        except Exception:
            logger.exception("error processing message from client %s", client.url)

    def _disconnect(self, client: WebSocket) -> None:
        """Remove client from room and clean up resources."""
        if client in self.clients:
            self.clients.remove(client)
            logger.info("client removed from room %s: %s", self.diff_id, client.url)

    async def _broadcast_to_room(
        self, message: bytes, exclude: WebSocket | None = None
    ) -> None:
        clients = self.clients.copy()
        disconnected_clients: list[WebSocket] = []

        for client in clients:
            if client == exclude:
                continue
            try:
                await client.send_bytes(message)
            except WebSocketDisconnect:
                logger.info("client disconnected during broadcast: %s", client.url)
                disconnected_clients.append(client)
            except ConnectionResetError:
                logger.warning("connection reset during broadcast: %s", client.url)
                disconnected_clients.append(client)
            except Exception:
                logger.exception(
                    "unexpected error broadcasting to client %s", client.url
                )
                disconnected_clients.append(client)

        # Clean up disconnected clients
        for client in disconnected_clients:
            self._disconnect(client)


class YWebSocketServer:
    def __init__(self) -> None:
        self.rooms: dict[str, YRoom] = {}

    async def async_serve(self, diff_id: str, client: WebSocket) -> None:
        try:
            doc = DiffDoc()
            room = self.rooms.setdefault(diff_id, YRoom(diff_id=diff_id, doc=doc))
            serve_task = asyncio.create_task(room.async_serve(client))
            broadcast_task = asyncio.create_task(room.async_broadcast_updates())
            await serve_task
            broadcast_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await broadcast_task
        except Exception:
            logger.exception("error in websocket server for diff %s", diff_id)
        finally:
            if diff_id in self.rooms and not self.rooms[diff_id].clients:
                logger.info("removing empty room: %s", diff_id)
                del self.rooms[diff_id]
