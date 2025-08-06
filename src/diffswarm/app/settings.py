from functools import cache
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    database_url: str = "sqlite:///diffswarm-dev.sqlite3"
    database_echo: bool = True
    database_connect_check_same_thread: bool = False
    database_poolclass: Literal["QueuePool", "StaticPool"] = "QueuePool"


@cache
def get_settings() -> Settings:
    return Settings()
