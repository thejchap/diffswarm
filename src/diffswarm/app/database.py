from functools import cache

from sapling import Database, SQLiteBackend

from .settings import get_settings


@cache
def get_database() -> Database:
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    backend = SQLiteBackend(path=db_path)
    return Database(backend=backend)
