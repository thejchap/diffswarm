"""
database utils/models.

- https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308
- https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances
- https://fastapi.tiangolo.com/tutorial/sql-databases/?h=database#create-a-hero
"""

from collections.abc import Generator
from typing import assert_never

from sqlalchemy import Pool, QueuePool, StaticPool, String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
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


class Base(DeclarativeBase):
    pass


class DBDiff(Base):
    """maps to the `diff` table in the database."""

    __tablename__: str = "diff"
    id: Mapped[str] = mapped_column(
        String(26),
        primary_key=True,
        nullable=False,
    )
    raw: Mapped[str] = mapped_column(
        Text(),
        nullable=False,
    )
