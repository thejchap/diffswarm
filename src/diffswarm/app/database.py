from functools import cache
from pathlib import Path

from sapling import Database, SQLiteBackend

from .settings import get_settings


@cache
def get_database() -> Database:
    settings = get_settings()
    db_path = settings.database_url.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    backend = SQLiteBackend(path=db_path)
    return Database(backend=backend)
