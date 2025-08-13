"""
database utils/models.

these models map directly to database rows.
pydantic models for the api should be converted into/from these models.

- https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308
- https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances
- https://fastapi.tiangolo.com/tutorial/sql-databases/?h=database#create-a-hero
"""

from collections.abc import Generator
from datetime import datetime
from sqlite3 import Connection as SQLite3Connection
from typing import assert_never

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Pool,
    QueuePool,
    StaticPool,
    String,
    Text,
    create_engine,
    event,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from .settings import Settings, get_settings


def _get_poolclass(settings: Settings) -> type[Pool]:
    match settings.database_poolclass:
        case "QueuePool":
            return QueuePool
        case "StaticPool":
            return StaticPool
    assert_never(settings.database_poolclass)


SETTINGS = get_settings()
# https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#using-a-memory-database-in-multiple-threads
ENGINE = create_engine(
    url=SETTINGS.database_url,
    echo=SETTINGS.database_echo,
    connect_args={"check_same_thread": SETTINGS.database_connect_check_same_thread},
    poolclass=_get_poolclass(SETTINGS),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def get_session() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@event.listens_for(ENGINE, "connect")
def set_sqlite_pragmas(
    dbapi_connection: SQLite3Connection,
    _,  # noqa: ANN001
) -> None:
    """https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-foreign-keys."""
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()

    # enforce fk constraints
    cursor.execute("PRAGMA foreign_keys=ON")

    # readers don't block writers
    # https://fly.io/blog/wal-mode-in-litefs/
    cursor.execute("PRAGMA journal_mode = WAL")

    # more performant, still safe in WAL mode
    # https://www.sqlite.org/pragma.html#pragma_synchronous
    cursor.execute("PRAGMA synchronous = NORMAL")

    # retry instead of SQLITE_BUSY
    cursor.execute("PRAGMA busy_timeout = 5000")

    cursor.close()
    dbapi_connection.autocommit = ac


class Base(DeclarativeBase):
    pass


class DBDiff(Base):
    """maps to the `diff` table in the database."""

    __tablename__: str = "diff"
    id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(id) == 28"),
        primary_key=True,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,  # Will default to id if None
    )
    raw: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    from_filename: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    from_timestamp: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    to_filename: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    to_timestamp: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,
    )
    # Relationship to hunks and comments
    hunks: Mapped[list["DBHunk"]] = relationship(
        "DBHunk", back_populates="diff", cascade="all, delete-orphan"
    )
    comments: Mapped[list["DBComment"]] = relationship(
        "DBComment", back_populates="diff", cascade="all, delete-orphan"
    )


class DBHunk(Base):
    """maps to the `hunk` table in the database."""

    __tablename__: str = "hunk"
    id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(id) == 28"),
        primary_key=True,
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(
        Text(),
        nullable=True,  # Will default to id if None
    )
    diff_id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(diff_id) == 28"),
        ForeignKey("diff.id"),
        nullable=False,
    )
    from_start: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    from_count: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    to_start: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    to_count: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(),
        nullable=True,
    )

    # Relationships
    diff: Mapped["DBDiff"] = relationship("DBDiff", back_populates="hunks")
    lines: Mapped[list["DBLine"]] = relationship(
        "DBLine", back_populates="hunk", cascade="all, delete-orphan"
    )
    comments: Mapped[list["DBComment"]] = relationship(
        "DBComment", back_populates="hunk", cascade="all, delete-orphan"
    )


class DBLine(Base):
    """maps to the `line` table in the database."""

    __tablename__: str = "line"
    id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(id) == 28"),
        primary_key=True,
        nullable=False,
    )
    hunk_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("hunk.id"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    line_number_old: Mapped[int | None] = mapped_column(
        Integer(),
        nullable=True,
    )
    line_number_new: Mapped[int | None] = mapped_column(
        Integer(),
        nullable=True,
    )

    # Relationship
    hunk: Mapped["DBHunk"] = relationship("DBHunk", back_populates="lines")


class DBComment(Base):
    """maps to the `comment` table in the database."""

    __tablename__: str = "comment"
    id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(id) == 28"),
        primary_key=True,
        nullable=False,
    )
    text: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
    author: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(),
        nullable=False,
        server_default=func.now(),
    )
    hunk_id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(hunk_id) == 28"),
        ForeignKey("hunk.id"),
        nullable=False,
    )
    diff_id: Mapped[str] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(diff_id) == 28"),
        ForeignKey("diff.id"),
        nullable=False,
    )
    line_index: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    start_offset: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    end_offset: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    in_reply_to: Mapped[str | None] = mapped_column(
        String(28),
        CheckConstraint("LENGTH(in_reply_to) == 28"),
        ForeignKey("comment.id"),
        nullable=True,
    )

    # Relationships
    hunk: Mapped["DBHunk"] = relationship("DBHunk", back_populates="comments")
    diff: Mapped["DBDiff"] = relationship("DBDiff", back_populates="comments")
    replies: Mapped[list["DBComment"]] = relationship(
        "DBComment",
        foreign_keys="DBComment.in_reply_to",
        back_populates="parent_comment",
        cascade="all, delete-orphan",
    )
    parent_comment: Mapped["DBComment | None"] = relationship(
        "DBComment",
        foreign_keys=[in_reply_to],
        back_populates="replies",
        remote_side=id,
    )
