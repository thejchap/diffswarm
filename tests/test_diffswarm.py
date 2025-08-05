from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND

from diffswarm.app import APP
from diffswarm.app.database import Base, get_session


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, Any]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, echo=True
    )
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


class TestPages:
    def test_get_home(self, client: TestClient) -> None:
        res = client.get("/")
        assert res.text == "diffswarm"

    @pytest.mark.skip
    def test_get_diff(self, client: TestClient) -> None:
        res = client.get("/diffs/01K16KWT9GKTX0F6E5TRFS1Z0G")
        assert res.status_code == HTTP_404_NOT_FOUND


class TestAPI:
    def test_get_diff(self, client: TestClient) -> None:
        res = client.get("/api/diffs/12345")
        assert res.status_code == HTTP_200_OK
