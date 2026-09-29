from functools import cache
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    port: int = 8000
    host: str = "localhost"
    forwarded_allow_ips: str | None = None
    git_hash: str = "dev"
    database_path: str = Field(
        default=".db/diffswarm.sqlite3", validation_alias="SAPLING_SQLITE_PATH"
    )


@cache
def get_settings() -> Settings:
    return Settings()
