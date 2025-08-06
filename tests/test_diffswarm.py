from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from starlette.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from ulid import ULID

from diffswarm import APP
from diffswarm.app.models import DiffBase


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

    def test_create_get_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == HTTP_201_CREATED, res.text
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/diffs/{diff_id}")
        assert res.status_code == HTTP_200_OK
        body = res.text
        assert "<html" in body


class TestAPI:
    def test_get_diff_invalid_id(self, client: TestClient) -> None:
        res = client.get("/api/diffs/12345")
        assert res.status_code == HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_diff_not_found(self, client: TestClient) -> None:
        res = client.get(f"/api/diffs/{ULID()}")
        assert res.status_code == HTTP_404_NOT_FOUND

    def test_create_get_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == HTTP_201_CREATED, res.text
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["id"] == diff_id
        assert diff["raw"] == DiffBase.HELLO_WORLD
