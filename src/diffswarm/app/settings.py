from functools import cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    database_url: str = "sqlite:///diffswarm-dev.sqlite3"
    database_echo: bool = True
    database_connect_check_same_thread: bool = True
    database_use_static_pool: bool = False


@cache
def get_settings() -> Settings:
    return Settings()
