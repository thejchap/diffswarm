import shutil
import subprocess
from functools import cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_git_hash() -> str:
    git = shutil.which("git")
    if not git:
        return "dev"
    try:
        result = subprocess.run(
            [git, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "dev"


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env")
    port: int = 8000
    host: str = "localhost"
    forwarded_allow_ips: str | None = None
    git_hash: str = _resolve_git_hash()


@cache
def get_settings() -> Settings:
    return Settings()
