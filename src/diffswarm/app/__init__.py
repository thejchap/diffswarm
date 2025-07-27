import uvicorn

from .app import APP


def run() -> None:
    uvicorn.run(APP)


__all__ = ["APP", "run"]
