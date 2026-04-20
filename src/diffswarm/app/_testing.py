from tryke_guard import __TRYKE_TESTING__

if __TRYKE_TESTING__:
    import os
    from collections.abc import Generator
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    @contextmanager
    def _client() -> Generator[TestClient]:
        # Lazy import to avoid circular dependency when routers import _client
        # at module-load time during tryke's test discovery.
        from diffswarm.app.app import APP  # noqa: PLC0415

        os.environ["SAPLING_SQLITE_PATH"] = ":memory:"
        with TestClient(APP) as client:
            yield client
