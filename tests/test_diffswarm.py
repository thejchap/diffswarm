from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.status import HTTP_200_OK

from diffswarm.app import APP
from diffswarm.app.database import Base, get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, Any]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient]:
    def get_session_override() -> Session:
        return session

    APP.dependency_overrides[get_session] = get_session_override
    client = TestClient(APP)
    yield client
    APP.dependency_overrides.clear()


def test_home(client: TestClient) -> None:
    res = client.get("/")
    assert res.text == "diffswarm"


def test_get_diff(client: TestClient) -> None:
    res = client.get("/api/diffs/12345")
    assert res.status_code == HTTP_200_OK
