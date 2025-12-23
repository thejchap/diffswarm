from functools import cache
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    port: int = 8000
    host: str = "localhost"
    forwarded_allow_ips: str | None = None

    @property
    def git_hash(self) -> str:
        revision_file = Path("REVISION")
        if revision_file.exists():
            return revision_file.read_text().strip()
        return "dev"


@cache
def get_settings() -> Settings:
    return Settings()
