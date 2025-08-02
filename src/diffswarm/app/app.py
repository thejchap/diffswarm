import logging
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Never

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.staticfiles import StaticFiles
from pycrdt import (
    Array,
    Doc,
    YMessageType,
    create_sync_message,  # pyright: ignore[reportUnknownVariableType]
)
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

from .database import ENGINE, Base
from .routers import PAGES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(ENGINE)
    yield


APP = FastAPI(lifespan=lifespan)
APP.include_router(PAGES)
APP.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)

DiffDoc = Doc[Array[int]]


class YWebSocketManager:
    def __init__(self) -> None:
        self.rooms: defaultdict[str, set[WebSocket]] = defaultdict(set)

    async def serve(self, websocket: WebSocket, room_name: str, doc: DiffDoc) -> None:
        await websocket.accept()
        self.rooms[room_name].add(websocket)
        sync_msg = create_sync_message(doc)
        await websocket.send_bytes(sync_msg)
        try:
            async for message in websocket.iter_bytes():
                if not message:
                    continue
                logger.info(YMessageType(message[0]).name)
        except Exception:
            logger.exception("bad")
        finally:
            self._disconnect(websocket, room_name)

    def _disconnect(self, websocket: WebSocket, room_name: str) -> None:
        if room_name in self.rooms:
            self.rooms[room_name].discard(websocket)
            if not self.rooms[room_name]:
                del self.rooms[room_name]

    async def _broadcast_to_room(
        self, message: bytes, room_name: str, exclude: WebSocket | None = None
    ) -> None:
        if room_name not in self.rooms:
            return
        for client in self.rooms[room_name]:
            if client == exclude:
                continue
            try:
                await client.send_bytes(message)
            except (WebSocketDisconnect, ConnectionResetError):
                self._disconnect(client, room_name)


MANAGER = YWebSocketManager()


@APP.websocket("/ws/{room_name}")
async def websocket_endpoint(websocket: WebSocket, room_name: str) -> None:
    doc = DiffDoc()
    await MANAGER.serve(websocket, room_name, doc)


@APP.exception_handler(NoResultFound)
def no_result_found_handler(_request: Request, _exc: NoResultFound) -> Never:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@APP.exception_handler(SQLAlchemyError)
def sql_alchemy_error_handler(_request: Request, _exc: SQLAlchemyError) -> Never:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
