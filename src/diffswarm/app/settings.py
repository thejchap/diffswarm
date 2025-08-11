from functools import cache
from pathlib import Path
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    database_url: str = "sqlite:///db/diffswarm-dev.sqlite3"
    database_echo: bool = True
    database_connect_check_same_thread: bool = False
    database_poolclass: Literal["QueuePool", "StaticPool"] = "QueuePool"
    database_create_all: bool = False
    port: int = 8000
    host: str = "localhost"

    @property
    def git_hash(self) -> str:
        revision_file = Path("REVISION")
        if revision_file.exists():
            return revision_file.read_text().strip()
        return "dev"


@cache
def get_settings() -> Settings:
    return Settings()
