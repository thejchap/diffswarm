from functools import cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    port: int = 8000
    host: str = "localhost"
    forwarded_allow_ips: str | None = None
    git_hash: str = "dev"


@cache
def get_settings() -> Settings:
    return Settings()
