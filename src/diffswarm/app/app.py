import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Never

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

from .database import ENGINE, Base
from .routers import PAGES, WEBSOCKETS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(ENGINE)
    yield


APP = FastAPI(lifespan=lifespan)
APP.include_router(PAGES)
APP.include_router(WEBSOCKETS)
APP.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


@APP.exception_handler(NoResultFound)
def no_result_found_handler(_request: Request, _exc: NoResultFound) -> Never:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@APP.exception_handler(SQLAlchemyError)
def sql_alchemy_error_handler(_request: Request, _exc: SQLAlchemyError) -> Never:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
