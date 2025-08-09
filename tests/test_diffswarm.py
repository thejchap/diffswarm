from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from starlette import status
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
        assert res.status_code == status.HTTP_404_NOT_FOUND

    def test_create_get_diff(self, client: TestClient) -> None:
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED, res.text
        diff_id = res.headers["X-Diff-ID"]
        res = client.get(f"/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.text
        assert "<html" in body


class TestAPI:
    def test_get_diff_invalid_id(self, client: TestClient) -> None:
        res = client.get("/api/diffs/12345")
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_diff_not_found(self, client: TestClient) -> None:
        res = client.get(f"/api/diffs/{ULID()}")
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

    def test_database_storage_and_retrieval(self, client: TestClient) -> None:
        """Test that structured diff data is properly stored and retrieved."""
        expected_to_count = 2
        expected_line_count = 2
        expected_add_line_number = 2

        # Create a diff via the API
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Retrieve and validate via API instead of direct database queries
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        diff = body["diff"]

        # Check diff structure
        assert diff["id"] == diff_id
        assert diff["raw"] == DiffBase.HELLO_WORLD
        assert diff["from_filename"] == "/dev/fd/14"
        assert diff["to_filename"] == "/dev/fd/16"
        assert diff["from_timestamp"] is not None
        assert diff["to_timestamp"] is not None

        # Check hunks structure
        assert len(diff["hunks"]) == 1
        hunk = diff["hunks"][0]
        assert hunk["from_start"] == 1
        assert hunk["from_count"] == 1
        assert hunk["to_start"] == 1
        assert hunk["to_count"] == expected_to_count

        # Check lines structure
        lines = hunk["lines"]
        assert len(lines) == expected_line_count

        # First line (context)
        context_line = next(line for line in lines if line["type"] == "CONTEXT")
        assert context_line["content"] == "hello"
        assert context_line["line_number_old"] == 1
        assert context_line["line_number_new"] == 1

        # Second line (add)
        add_line = next(line for line in lines if line["type"] == "ADD")
        assert add_line["content"] == "world"
        assert add_line["line_number_old"] is None
        assert add_line["line_number_new"] == expected_add_line_number

    def test_create_comment(self, client: TestClient) -> None:
        """Test creating a comment on a diff."""
        # First create a diff
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Get the diff to extract hunk ID
        res = client.get(f"/api/diffs/{diff_id}")
        assert res.status_code == status.HTTP_200_OK
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]

        # Create a comment
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

    def test_list_comments_by_diff(self, client: TestClient) -> None:
        """Test listing comments for a diff."""
        # Create a diff
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Get hunk ID
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]

        # Create two comments
        comment1_data = {
            "text": "First comment",
            "author": "user1",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 3,
        }
        res = client.post("/api/comments", json=comment1_data)
        assert res.status_code == status.HTTP_200_OK

        comment2_data = {
            "text": "Second comment",
            "author": "user2",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 1,
            "start_offset": 0,
            "end_offset": 5,
        }
        res = client.post("/api/comments", json=comment2_data)
        assert res.status_code == status.HTTP_200_OK

        # List comments for diff
        res = client.get(f"/api/diffs/{diff_id}/comments")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        comments = body["comments"]
        expected_comment_count = 2
        assert len(comments) == expected_comment_count
        assert comments[0]["text"] == "First comment"
        assert comments[1]["text"] == "Second comment"

    def test_list_comments_by_hunk(self, client: TestClient) -> None:
        """Test listing comments for a hunk."""
        # Create a diff
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Get hunk ID
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]

        # Create a comment
        comment_data = {
            "text": "Hunk-specific comment",
            "author": "hunk_user",
            "hunk_id": str(hunk_id),
            "diff_id": diff_id,
            "line_index": 0,
            "start_offset": 0,
            "end_offset": 4,
        }
        res = client.post("/api/comments", json=comment_data)
        assert res.status_code == status.HTTP_200_OK

        # List comments for hunk
        res = client.get(f"/api/hunks/{hunk_id}/comments")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        comments = body["comments"]
        assert len(comments) == 1
        assert comments[0]["text"] == "Hunk-specific comment"
        assert comments[0]["author"] == "hunk_user"

    def test_delete_comment(self, client: TestClient) -> None:
        """Test deleting a comment."""
        # Create a diff
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Get hunk ID
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]

        # Create a comment
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

        # Delete the comment
        res = client.delete(f"/api/comments/{comment_id}")
        assert res.status_code == status.HTTP_200_OK
        body = res.json()
        assert body["message"] == "Comment deleted successfully"

        # Verify comment is deleted by trying to list comments for diff
        res = client.get(f"/api/diffs/{diff_id}/comments")
        assert res.status_code == status.HTTP_200_OK
        comments = res.json()["comments"]
        assert len(comments) == 0

    def test_delete_comment_not_found(self, client: TestClient) -> None:
        """Test deleting a non-existent comment returns 404."""
        fake_comment_id = str(ULID())
        res = client.delete(f"/api/comments/{fake_comment_id}")
        assert res.status_code == status.HTTP_404_NOT_FOUND
        body = res.json()
        assert body["detail"] == "Comment not found"

    def test_create_reply_comment(self, client: TestClient) -> None:
        """Test creating a reply to another comment."""
        # Create a diff
        res = client.post(
            "/",
            content=DiffBase.HELLO_WORLD,
            headers={"Content-Type": "text/plain"},
        )
        assert res.status_code == status.HTTP_201_CREATED
        diff_id = res.headers["X-Diff-ID"]

        # Get hunk ID
        res = client.get(f"/api/diffs/{diff_id}")
        diff = res.json()["diff"]
        hunk_id = diff["hunks"][0]["id"]

        # Create parent comment
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

        # Create reply comment
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

        # List comments and verify both are there
        res = client.get(f"/api/diffs/{diff_id}/comments")
        assert res.status_code == status.HTTP_200_OK
        comments = res.json()["comments"]
        expected_comment_count = 2
        assert len(comments) == expected_comment_count
