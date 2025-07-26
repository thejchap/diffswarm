from fastapi import FastAPI

from .routers import PAGES

APP = FastAPI()
APP.include_router(PAGES)
