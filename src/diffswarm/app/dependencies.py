from collections.abc import Generator
from typing import Annotated

from fastapi import Depends

from .database import Database, get_database
from .settings import Settings, get_settings


def get_transaction() -> Generator[Database]:
    with get_database().transaction() as txn:
        yield txn


TransactionDependency = Annotated[Database, Depends(get_transaction)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
