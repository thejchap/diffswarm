from functools import cache

from sapling import Database, SQLiteBackend

from .settings import get_settings


@cache
def get_database() -> Database:
    settings = get_settings()
    backend = SQLiteBackend(path=settings.database_url)
    return Database(backend=backend)
