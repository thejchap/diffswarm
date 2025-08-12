import uvicorn

from diffswarm.app.settings import get_settings

from .app import APP


def server() -> None:
    settings = get_settings()
    uvicorn.run(
        APP,
        host=settings.host,
        port=settings.port,
        proxy_headers=True,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )


__all__ = ["APP", "server"]
