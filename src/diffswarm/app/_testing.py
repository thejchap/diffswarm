from tryke_guard import __TRYKE_TESTING__

if __TRYKE_TESTING__:
    from collections.abc import Generator
    from contextlib import contextmanager
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from diffswarm.app.settings import Settings

    @contextmanager
    def _client() -> Generator[TestClient]:
        # Lazy import to avoid circular dependency when routers import _client
        # at module-load time during tryke's test discovery.
        from diffswarm.app.app import APP  # noqa: PLC0415

        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.sqlite3")

            with (
                patch(
                    "diffswarm.app.database.get_settings",
                    return_value=Settings.model_validate({"SAPLING_SQLITE_PATH": path}),
                ),
                TestClient(APP) as client,
            ):
                yield client
