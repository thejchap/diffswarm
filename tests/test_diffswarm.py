from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND
from ulid import ULID

from diffswarm import APP


@pytest.fixture(name="client")
def client_fixture() -> Generator[TestClient]:
    with TestClient(APP) as client:
        yield client


class TestPages:
    def test_get_home(self, client: TestClient) -> None:
        res = client.get("/")
        assert res.text == "diffswarm"

    def test_get_diff_not_found(self, client: TestClient) -> None:
        res = client.get(f"/diffs/{ULID()}")
        assert res.status_code == HTTP_404_NOT_FOUND


class TestAPI:
    def test_get_diff(self, client: TestClient) -> None:
        res = client.get("/api/diffs/12345")
        assert res.status_code == HTTP_200_OK
        body = res.json()
        assert "diff" in body
