from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Never

from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy.exc import NoResultFound, SQLAlchemyError

from .database import ENGINE, Base
from .routers import PAGES


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    Base.metadata.create_all(ENGINE)
    yield


APP = FastAPI(lifespan=lifespan)
APP.include_router(PAGES)


@APP.exception_handler(NoResultFound)
def no_result_found_handler(_request: Request, _exc: NoResultFound) -> Never:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@APP.exception_handler(SQLAlchemyError)
def sql_alchemy_error_handler(_request: Request, _exc: SQLAlchemyError) -> Never:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
