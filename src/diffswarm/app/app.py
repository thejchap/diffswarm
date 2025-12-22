import logging
from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sapling.errors import NotFoundError

from .routers import API, PAGES

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

APP = FastAPI()
APP.add_middleware(GZipMiddleware)
APP.include_router(PAGES)
APP.include_router(API, prefix="/api")
APP.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="static",
)


@APP.exception_handler(NotFoundError)
def not_found_error_handler(_request: Request, _exc: NotFoundError) -> Exception:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
