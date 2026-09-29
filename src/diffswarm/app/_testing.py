from tryke_guard import __TRYKE_TESTING__

if __TRYKE_TESTING__:
    from collections.abc import Generator
    from contextlib import contextmanager
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from diffswarm.app.database import Database
    from diffswarm.app.dependencies import get_transaction

    @contextmanager
    def _client() -> Generator[TestClient]:
        # Lazy import to avoid circular dependency when routers import _client
        # at module-load time during tryke's test discovery.
        from diffswarm.app.app import APP  # noqa: PLC0415

        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.sqlite3")

            def transaction() -> Generator[Database]:
                with Database(path=path, check_same_thread=False).transaction() as txn:
                    yield txn

            with (
                patch.dict(APP.dependency_overrides, {get_transaction: transaction}),
                TestClient(APP) as client,
            ):
                yield client
