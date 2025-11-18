import logging
from pathlib import Path

from fastapi import (
    FastAPI,
)
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

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
