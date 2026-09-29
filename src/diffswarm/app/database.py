from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, connect
from typing import Self

from sapling.backends.sqlite import SQLiteBackend
from tryke_guard import __TRYKE_TESTING__

from .models import Comment, Hunk, Line
from .settings import get_settings


class Database(SQLiteBackend):
    """A request-owned SQLite connection, closed when its transaction ends."""

    @property
    def connection(self) -> Connection:
        if self._conn is None:
            msg = "Database connection is not open"
            raise RuntimeError(msg)
        return self._conn

    def initialize(self) -> None:
        """Open a connection without issuing schema writes in request handlers."""
        if self._conn is None:
            self._conn = connect(
                self.path,
                timeout=self.timeout,
                detect_types=self.detect_types,
                isolation_level=self.isolation_level,
                check_same_thread=self.check_same_thread,
                cached_statements=self.cached_statements,
                uri=self.uri,
            )
            self._initialized = True

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
            self._initialized = False

    def initialize_schema(self) -> None:
        """Create Sapling's schema and relationship indexes once at startup."""
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self.initialize()
            self._init_schema()
            with self.connection:
                self.connection.execute(
                    """CREATE INDEX IF NOT EXISTS document_diff_id
                    ON document (
                        model_class, json_extract(model, '$.diff_id'), model_id
                    )
                    """
                )
                self.connection.execute(
                    """CREATE INDEX IF NOT EXISTS document_hunk_id
                    ON document (
                        model_class, json_extract(model, '$.hunk_id'), model_id
                    )
                    """
                )
        finally:
            self.close()

    @contextmanager
    def transaction(self) -> Generator[Self]:
        try:
            self.initialize()
            with self.connection:
                # Reserve the writer before reading to serialize read/modify/write.
                self.connection.execute("BEGIN IMMEDIATE")
                yield self
        finally:
            self.close()

    @contextmanager
    def read_transaction(self) -> Generator[Self]:
        try:
            self.initialize()
            self.connection.execute("PRAGMA query_only = ON")
            with self.connection:
                self.connection.execute("BEGIN")
                yield self
        finally:
            self.close()

    def hunks_for_diff(self, diff_id: str) -> list[Hunk]:
        cursor = self.connection.execute(
            """SELECT model FROM document
            WHERE model_class = 'Hunk' AND json_extract(model, '$.diff_id') = ?
            ORDER BY model_id""",
            (diff_id,),
        )
        return [Hunk.model_validate_json(row[0]) for row in cursor]

    def lines_for_diff(self, diff_id: str) -> list[Line]:
        # Unary + removes the column's TEXT affinity, matching json_extract's
        # expression affinity so SQLite can use document_hunk_id for the join.
        cursor = self.connection.execute(
            """SELECT line.model FROM document AS hunk
            JOIN document AS line
              ON line.model_class = 'Line'
              AND json_extract(line.model, '$.hunk_id') = +hunk.model_id
            WHERE hunk.model_class = 'Hunk'
              AND json_extract(hunk.model, '$.diff_id') = ?
            ORDER BY hunk.model_id, line.model_id""",
            (diff_id,),
        )
        return [Line.model_validate_json(row[0]) for row in cursor]

    def comments_for_diff(self, diff_id: str) -> list[Comment]:
        cursor = self.connection.execute(
            """SELECT model FROM document
            WHERE model_class = 'Comment' AND json_extract(model, '$.diff_id') = ?
            ORDER BY model_id""",
            (diff_id,),
        )
        return [Comment.model_validate_json(row[0]) for row in cursor]


def get_database() -> Database:
    # FastAPI may enter, execute, and exit a dependency on different worker threads.
    # Each request owns this connection exclusively despite those thread changes.
    return Database(path=get_settings().database_path, check_same_thread=False)


if __TRYKE_TESTING__:
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
            Database(path=path).initialize_schema()
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

    @test(name="read transactions reject writes and close on success and failure")
    def test_read_transaction_lifecycle() -> None:
        from sqlite3 import OperationalError  # noqa: PLC0415

        with TemporaryDirectory() as directory:
            database = Database(path=str(Path(directory) / "test.sqlite3"))
            database.initialize_schema()
            with database.read_transaction() as txn:
                connection = txn.connection
                expect(lambda: txn.put(_Record, "bad", _Record(value="bad"))).to_raise(
                    OperationalError, match="readonly"
                )
            expect(lambda: connection.execute("SELECT 1")).to_raise(
                ProgrammingError, match="closed"
            )

            def fail_read() -> None:
                with database.read_transaction():
                    msg = "Read failed"
                    raise ValueError(msg)

            expect(fail_read).to_raise(ValueError, match="Read failed")
            expect(lambda: database.connection).to_raise(RuntimeError, match="not open")
            with database.transaction() as txn:
                txn.put(_Record, "good", _Record(value="saved"))
            with database.read_transaction() as txn:
                expect(txn.get(_Record, "bad")).to_be_none()
                expect(txn.fetch(_Record, "good").model.value).to_equal("saved")

    @test(name="readers coexist with a writer and retain a consistent snapshot")
    def test_concurrent_read_write() -> None:
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415
        from threading import Event  # noqa: PLC0415

        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.sqlite3")
            Database(path=path).initialize_schema()
            with Database(path=path).transaction() as txn:
                txn.put(_Record, "record", _Record(value="before"))
            writing = Event()
            finish = Event()

            def write() -> None:
                with Database(path=path).transaction() as txn:
                    txn.put(_Record, "record", _Record(value="after"))
                    writing.set()
                    expect(finish.wait(timeout=5)).to_be_truthy()

            with ThreadPoolExecutor(max_workers=1) as executor:
                with Database(path=path).read_transaction() as reader:
                    expect(reader.fetch(_Record, "record").model.value).to_equal(
                        "before"
                    )
                    future = executor.submit(write)
                    try:
                        expect(writing.wait(timeout=5)).to_be_truthy()
                        with Database(path=path, timeout=0).read_transaction() as other:
                            expect(other.fetch(_Record, "record").model.value).to_equal(
                                "before"
                            )
                        expect(reader.fetch(_Record, "record").model.value).to_equal(
                            "before"
                        )
                    finally:
                        finish.set()
                future.result(timeout=5)
            with Database(path=path).read_transaction() as txn:
                expect(txn.fetch(_Record, "record").model.value).to_equal("after")

    @test(name="failure to acquire a write transaction closes its connection")
    def test_failed_begin_cleanup() -> None:
        from sqlite3 import OperationalError  # noqa: PLC0415

        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "test.sqlite3")
            Database(path=path).initialize_schema()
            blocked = Database(path=path, timeout=0)

            def begin_write() -> None:
                with blocked.transaction():
                    pass

            with Database(path=path).transaction():
                expect(begin_write).to_raise(OperationalError, match="locked")
            expect(lambda: blocked.connection).to_raise(RuntimeError, match="not open")
