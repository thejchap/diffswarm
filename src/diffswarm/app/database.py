from collections.abc import Generator
from contextlib import contextmanager
from sqlite3 import Connection
from typing import Self

from sapling.backends.sqlite import SQLiteBackend
from tryke_guard import __TRYKE_TESTING__

from .settings import get_settings


class Database(SQLiteBackend):
    """A request-owned SQLite connection, closed when its transaction ends."""

    @property
    def connection(self) -> Connection:
        if self._conn is None:
            msg = "Database connection is not open"
            raise RuntimeError(msg)
        return self._conn

    @contextmanager
    def transaction(self) -> Generator[Self]:
        try:
            self.initialize()
            with self.connection:
                # Reserve the writer before reading, so concurrent read/modify/write
                # requests cannot overwrite each other's changes or upgrade locks.
                self.connection.execute("BEGIN IMMEDIATE")
                yield self
        finally:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
                self._initialized = False


def get_database() -> Database:
    # FastAPI may enter, execute, and exit a dependency on different worker threads.
    # Each request owns this connection exclusively despite those thread changes.
    return Database(path=get_settings().database_path, check_same_thread=False)


if __TRYKE_TESTING__:
    from pathlib import Path
    from sqlite3 import ProgrammingError
    from tempfile import TemporaryDirectory

    from pydantic import BaseModel
    from tryke import expect, test

    class _Record(BaseModel):
        value: str

    @test(name="request transactions commit rollback and close their connections")
    def test_transaction_lifecycle() -> None:
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.sqlite3")
            with Database(path=path).transaction() as txn:
                first_connection = txn.connection
                txn.put(_Record, "committed", _Record(value="saved"))

            expect(lambda: first_connection.execute("SELECT 1")).to_raise(
                ProgrammingError, match="closed"
            )

            rolled_back = Database(path=path)

            def fail_transaction() -> None:
                with rolled_back.transaction() as txn:
                    txn.put(_Record, "rolled-back", _Record(value="discard"))
                    msg = "Abort transaction"
                    raise ValueError(msg)

            expect(fail_transaction).to_raise(ValueError, match="Abort transaction")
            expect(lambda: rolled_back.connection).to_raise(
                RuntimeError, match="not open"
            )

            with Database(path=path).transaction() as txn:
                expect(txn.connection is first_connection).to_be_falsy()
                expect(txn.fetch(_Record, "committed").model.value).to_equal("saved")
                expect(txn.get(_Record, "rolled-back")).to_be_none()
