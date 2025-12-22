from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sapling.backends.base import Backend

from .database import get_database
from .settings import Settings, get_settings


def get_transaction() -> Generator[Backend]:
    yield from get_database().transaction_dependency()


TransactionDependency = Annotated[Backend, Depends(get_transaction)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
