"""
database utils/models.

- https://medium.com/@tclaitken/setting-up-a-fastapi-app-with-async-sqlalchemy-2-0-pydantic-v2-e6c540be4308
- https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances
- https://fastapi.tiangolo.com/tutorial/sql-databases/?h=database#create-a-hero
"""

from collections.abc import Generator

from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    sessionmaker,
)

from .settings import get_settings

ENGINE = create_engine(url=get_settings().database_url, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


class Base(DeclarativeBase):
    pass


class DBDiff(Base):
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


def get_session() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
