from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter, ValidationError
from starlette import status

from diffswarm import APP
from diffswarm.app.models import DiffBase, PrefixedULID, generate_prefixed_ulid

# Constants
PREFIXED_ULID_LENGTH = 28  # prefix + hyphen + 26 character ULID


@pytest.fixture(name="client")
def client_fixture() -> Generator[TestClient]:
    with TestClient(APP) as client:
        yield client


class TestPages:
    def test_get_home(self, client: TestClient) -> None:
        res = client.get("/")
        assert res.status_code == status.HTTP_200_OK
        assert "diffswarm" in res.text
        assert "<html" in res.text

    def test_get_diff_not_found(self, client: TestClient) -> None:
        res = client.get(f"/diffs/{generate_prefixed_ulid('d')}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_create_get_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED, res.text
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.text
        assert "<html" in body

    def test_delete_diff_pages(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        res = client.delete(f"/{diff_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.get(f"/{diff_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_diff_not_found_pages(self, client: TestClient) -> None:
        res = client.delete(f"/{generate_prefixed_ulid('d')}")
        assert res.status_code == status.HTTP_404_NOT_FOUND


class TestAPI:
    def test_get_diff_invalid_id(self, client: TestClient) -> None:
        res = client.get("/api/diffs/12345")
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_diff_not_found(self, client: TestClient) -> None:
        res = client.get(f"/api/diffs/{generate_prefixed_ulid('d')}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_create_get_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED, res.text
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["id"] == diff_id
        assert diff["raw"] == DiffBase.HELLO_WORLD
        assert diff["from_filename"] == "/dev/fd/14"
        assert diff["to_filename"] == "/dev/fd/16"
        assert diff["description"] is None  # Default should be None
        assert len(diff["hunks"]) == 1

        hunk = diff["hunks"][0]
        expected_to_count = 2
        expected_line_count = 2
        expected_new_line_number = 2

        assert hunk["from_start"] == 1
        assert hunk["from_count"] == 1
        assert hunk["to_start"] == 1
        assert hunk["to_count"] == expected_to_count
        assert len(hunk["lines"]) == expected_line_count

        lines = hunk["lines"]
        assert lines[0]["type"] == "CONTEXT"
        assert lines[0]["content"] == "hello"
        assert lines[0]["line_number_old"] == 1
        assert lines[0]["line_number_new"] == 1

        assert lines[1]["type"] == "ADD"
        assert lines[1]["content"] == "world"
        assert lines[1]["line_number_old"] is None
        assert lines[1]["line_number_new"] == expected_new_line_number

        # Test that line IDs are returned
        assert "id" in lines[0]
        assert "id" in lines[1]
        assert lines[0]["id"].startswith("l-")
        assert lines[1]["id"].startswith("l-")
        assert len(lines[0]["id"]) == PREFIXED_ULID_LENGTH
        assert len(lines[1]["id"]) == PREFIXED_ULID_LENGTH

    def test_database_storage_and_retrieval(self, client: TestClient) -> None:
        expected_to_count = 2
        expected_line_count = 2
        expected_add_line_number = 2
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["id"] == diff_id
        assert diff["raw"] == DiffBase.HELLO_WORLD
        assert diff["from_filename"] == "/dev/fd/14"
        assert diff["to_filename"] == "/dev/fd/16"
        assert diff["from_timestamp"] is not None
        assert diff["to_timestamp"] is not None
        assert len(diff["hunks"]) == 1
        hunk = diff["hunks"][0]
        assert hunk["from_start"] == 1
        assert hunk["from_count"] == 1
        assert hunk["to_start"] == 1
        assert hunk["to_count"] == expected_to_count
        lines = hunk["lines"]
        assert len(lines) == expected_line_count
        context_line = next(line for line in lines if line["type"] == "CONTEXT")
        assert context_line["content"] == "hello"
        assert context_line["line_number_old"] == 1
        assert context_line["line_number_new"] == 1
        add_line = next(line for line in lines if line["type"] == "ADD")
        assert add_line["content"] == "world"
        assert add_line["line_number_old"] is None
        assert add_line["line_number_new"] == expected_add_line_number

        # Test that line IDs are present and properly formatted
        assert "id" in context_line
        assert "id" in add_line
        assert context_line["id"].startswith("l-")
        assert add_line["id"].startswith("l-")
        assert len(context_line["id"]) == PREFIXED_ULID_LENGTH
        assert len(add_line["id"]) == PREFIXED_ULID_LENGTH

    def test_create_comment(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        comment_data = {
            "text": "This is a test comment",
            "author": "test_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 5,
        }
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        comment = body["comment"]
        assert comment["text"] == "This is a test comment"
        assert comment["author"] == "test_user"
        assert comment["diff_id"] == diff_id
        assert comment["line_index"] == 0
        assert comment["start_offset"] == 0
        expected_end_offset = 5
        assert comment["end_offset"] == expected_end_offset
        assert comment["in_reply_to"] is None
        assert "id" in comment
        assert "timestamp" in comment

    def test_delete_comment(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        comment_data = {
            "text": "Comment to delete",
            "author": "delete_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 7,
        }
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK
        comment_id = res.json()["comment"]["id"]
        res = client.delete(f"/api/comments/{comment_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.delete(f"/api/comments/{comment_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_comment_not_found(self, client: TestClient) -> None:
        res = client.delete(f"/api/comments/{generate_prefixed_ulid('d')}")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Comment not found"

    def test_create_reply_comment(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        parent_comment_data = {
            "text": "Parent comment",
            "author": "parent_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 3,
        }
        res = client.post("/api/comments", json=parent_comment_data)
        assert res.status_code == status.HTTP_200_OK
        parent_comment_id = res.json()["comment"]["id"]
        reply_comment_data = {
            "text": "Reply comment",
            "author": "reply_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 3,
            "in_reply_to": parent_comment_id,
        }
        res = client.post("/api/comments", json=reply_comment_data)
        assert res.status_code == status.HTTP_200_OK

        reply_comment = res.json()["comment"]
        assert reply_comment["text"] == "Reply comment"
        assert reply_comment["author"] == "reply_user"
        assert reply_comment["in_reply_to"] == parent_comment_id

        reply_comment_id = reply_comment["id"]
        res = client.delete(f"/api/comments/{reply_comment_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.delete(f"/api/comments/{parent_comment_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT

    def test_update_diff_name(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        update_data = {"name": "My Custom Diff Name"}
        res = client.put(f"/api/diffs/{diff_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["name"] == "My Custom Diff Name"
        assert diff["id"] == diff_id

    def test_update_diff_not_found(self, client: TestClient) -> None:
        update_data = {"name": "Test Name"}
        res = client.put(f"/api/diffs/{generate_prefixed_ulid('d')}", json=update_data)
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Diff not found"

    def test_update_diff_description(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Test setting description
        update_data = {"description": "This is a test description"}
        res = client.put(f"/api/diffs/{diff_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["description"] == "This is a test description"
        assert diff["id"] == diff_id

        # Test updating description
        update_data = {"description": "Updated description"}
        res = client.put(f"/api/diffs/{diff_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["description"] == "Updated description"

        # Test clearing description
        update_data = {"description": None}
        res = client.put(f"/api/diffs/{diff_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["description"] is None

    def test_update_diff_name_and_description(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Test updating both name and description
        update_data = {"name": "Custom Diff", "description": "Custom description"}
        res = client.put(f"/api/diffs/{diff_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]
        assert diff["name"] == "Custom Diff"
        assert diff["description"] == "Custom description"
        assert diff["id"] == diff_id

    def test_update_hunk_name(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        update_data = {"name": "My Custom Hunk Name"}
        res = client.put(f"/api/hunks/{hunk_id}", json=update_data)
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        hunk = body["hunk"]
        assert hunk["name"] == "My Custom Hunk Name"
        assert hunk["id"] == hunk_id

    def test_update_hunk_not_found(self, client: TestClient) -> None:
        update_data = {"name": "Test Name"}
        res = client.put(f"/api/hunks/{generate_prefixed_ulid('h')}", json=update_data)
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Hunk not found"

    def test_delete_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        res = client.delete(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_diff_not_found(self, client: TestClient) -> None:
        res = client.delete(f"/api/diffs/{generate_prefixed_ulid('d')}")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Diff not found"

    def test_cascade_delete_diff_deletes_hunks_lines_comments(
        self, client: TestClient
    ) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        assert len(diff["hunks"]) == 1
        expected_line_count = 2
        assert len(diff["hunks"][0]["lines"]) == expected_line_count
        comment_data = {
            "text": "Test comment",
            "author": "test_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 5,
        }
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK
        comment_id = res.json()["comment"]["id"]
        res = client.delete(f"/api/comments/{comment_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK
        comment_id_2 = res.json()["comment"]["id"]
        res = client.delete(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        res = client.delete(f"/api/comments/{comment_id_2}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_cascade_delete_comment_deletes_replies(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        parent_comment_data = {
            "text": "Parent comment",
            "author": "parent_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 3,
        }
        res = client.post("/api/comments", json=parent_comment_data)
        assert res.status_code == status.HTTP_200_OK
        parent_comment_id = res.json()["comment"]["id"]
        reply_comment_data = {
            "text": "Reply comment",
            "author": "reply_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 3,
            "in_reply_to": parent_comment_id,
        }
        res = client.post("/api/comments", json=reply_comment_data)
        assert res.status_code == status.HTTP_200_OK
        reply_comment_id = res.json()["comment"]["id"]
        res = client.delete(f"/api/comments/{parent_comment_id}")
        assert res.status_code == status.HTTP_204_NO_CONTENT
        res = client.delete(f"/api/comments/{reply_comment_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_toggle_hunk_completion(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]
        assert diff["hunks"][0]["completed_at"] is None
        completed_at = datetime.now(UTC).isoformat()
        res = client.put(f"/api/hunks/{hunk_id}", json={"completed_at": completed_at})
        assert res.status_code == status.HTTP_200_OK
        hunk = res.json()["hunk"]
        assert hunk["completed_at"] is not None
        res = client.put(f"/api/hunks/{hunk_id}", json={"completed_at": None})
        assert res.status_code == status.HTTP_200_OK
        hunk = res.json()["hunk"]
        assert hunk["completed_at"] is None

    def test_toggle_hunk_completion_not_found(self, client: TestClient) -> None:
        completed_at = datetime.now(UTC).isoformat()
        res = client.put(
            f"/api/hunks/{generate_prefixed_ulid('h')}",
            json={"completed_at": completed_at},
        )
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Hunk not found"


class TestParser:
    def test_1(self) -> None:
        with Path.open(Path(__file__).parent / "fixtures/1.diff") as f:
            diff = f.read()

        assert DiffBase.parse_str(diff)

    def test_2(self) -> None:
        with Path.open(Path(__file__).parent / "fixtures/2.diff") as f:
            diff = f.read()

        assert DiffBase.parse_str(diff)


class TestPrefixedULID:
    ta = TypeAdapter[PrefixedULID](PrefixedULID)

    def validate(self, val: str) -> str:
        return self.ta.validate_python(val)

    def test_lower(self) -> None:
        val = "a-01BX5ZZKBKACTAV9WEVGEMMVRZ"
        assert self.validate(val) == val.lower()

    def test_invalid(self) -> None:
        val = "a-01BX5ZZKBKACTAV9"
        with pytest.raises(ValidationError):
            assert self.validate(val) == val.lower()

    def test_identity(self) -> None:
        val = generate_prefixed_ulid("a")
        assert self.validate(val) == val
