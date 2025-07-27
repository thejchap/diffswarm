from functools import cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    database_url: str = "sqlite:///diffswarm-dev.sqlite3"


@cache
def get_settings() -> Settings:
    return Settings()
