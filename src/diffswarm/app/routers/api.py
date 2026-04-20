from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sapling.errors import NotFoundError
from tryke_guard import __TRYKE_TESTING__

from diffswarm.app.dependencies import TransactionDependency
from diffswarm.app.models import (
    Comment,
    Diff,
    DiffSwarmBaseModel,
    Hunk,
    Line,
    PrefixedULID,
    generate_prefixed_ulid,
)

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: Diff


class CreateCommentRequest(DiffSwarmBaseModel):
    text: str
    author: str
    hunk_id: PrefixedULID
    diff_id: PrefixedULID
    line_index: int
    start_offset: int
    end_offset: int
    in_reply_to: PrefixedULID | None = None


class CreateCommentResponse(DiffSwarmBaseModel):
    comment: Comment


class UpdateDiffRequest(DiffSwarmBaseModel):
    name: str | None = None
    description: str | None = None


class UpdateDiffResponse(DiffSwarmBaseModel):
    diff: Diff


class UpdateHunkRequest(DiffSwarmBaseModel):
    name: str | None = None
    completed_at: datetime | None = None


class UpdateHunkResponse(DiffSwarmBaseModel):
    hunk: Hunk


class UpdateCommentRequest(DiffSwarmBaseModel):
    text: str


class UpdateCommentResponse(DiffSwarmBaseModel):
    comment: Comment


def load_diff_with_relations(txn: TransactionDependency, diff_id: str) -> Diff:
    diff_doc = txn.fetch(Diff, diff_id)
    diff = diff_doc.model
    all_hunks = txn.all(Hunk)
    hunks_for_diff = [h.model for h in all_hunks if h.model.diff_id == diff_id]
    all_lines = txn.all(Line)
    for hunk in hunks_for_diff:
        lines = [line.model for line in all_lines if line.model.hunk_id == hunk.id_]
        hunk.lines = sorted(
            lines,
            key=lambda line: (
                line.line_number_old
                if line.line_number_old is not None
                else float("inf"),
                line.line_number_new
                if line.line_number_new is not None
                else float("inf"),
            ),
        )
    diff.hunks = hunks_for_diff
    return diff


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: PrefixedULID, txn: TransactionDependency) -> GetDiffResponse:
    diff = load_diff_with_relations(txn, diff_id)
    return GetDiffResponse(diff=diff)


@ROUTER.post("/comments")
def create_comment(
    request: CreateCommentRequest, txn: TransactionDependency
) -> CreateCommentResponse:
    comment_id = generate_prefixed_ulid("c")
    comment = Comment(
        id=comment_id,
        text=request.text,
        author=request.author,
        timestamp=datetime.now(UTC),
        hunk_id=request.hunk_id,
        diff_id=request.diff_id,
        line_index=request.line_index,
        start_offset=request.start_offset,
        end_offset=request.end_offset,
        in_reply_to=request.in_reply_to,
    )
    comment_doc = txn.put(Comment, comment_id, comment)
    return CreateCommentResponse(comment=comment_doc.model)


@ROUTER.put("/comments/{comment_id}")
def update_comment(
    comment_id: PrefixedULID, request: UpdateCommentRequest, txn: TransactionDependency
) -> UpdateCommentResponse:
    comment_doc = txn.get(Comment, comment_id)
    if not comment_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    updated_comment = comment_doc.model.model_copy(update={"text": request.text})
    comment_doc = txn.put(Comment, comment_id, updated_comment)
    return UpdateCommentResponse(comment=comment_doc.model)


@ROUTER.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: PrefixedULID, txn: TransactionDependency) -> None:
    comment_doc = txn.get(Comment, comment_id)
    if not comment_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    all_comments = txn.all(Comment)
    reply_ids = [c.model_id for c in all_comments if c.model.in_reply_to == comment_id]
    txn.delete_many(Comment, reply_ids)
    txn.delete(Comment, comment_id)


@ROUTER.put("/diffs/{diff_id}")
def update_diff(
    diff_id: PrefixedULID, request: UpdateDiffRequest, txn: TransactionDependency
) -> UpdateDiffResponse:
    try:
        diff = load_diff_with_relations(txn, diff_id)
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found"
        ) from None
    updates: dict[str, str | None] = {}
    if request.name is not None:
        updates["name"] = request.name
    if "description" in request.model_fields_set:
        updates["description"] = request.description
    updated_diff = diff.model_copy(update=updates)
    txn.put(Diff, diff_id, updated_diff)
    diff = load_diff_with_relations(txn, diff_id)
    return UpdateDiffResponse(diff=diff)


@ROUTER.put("/hunks/{hunk_id}")
def update_hunk(
    hunk_id: PrefixedULID, request: UpdateHunkRequest, txn: TransactionDependency
) -> UpdateHunkResponse:
    hunk_doc = txn.get(Hunk, hunk_id)
    if not hunk_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Hunk not found"
        )
    hunk = hunk_doc.model
    all_lines = txn.all(Line)
    hunk.lines = [line.model for line in all_lines if line.model.hunk_id == hunk_id]
    updates: dict[str, str | datetime | None] = {}
    if request.name is not None:
        updates["name"] = request.name
    if "completed_at" in request.model_fields_set:
        updates["completed_at"] = request.completed_at
    updated_hunk = hunk.model_copy(update=updates)
    txn.put(Hunk, hunk_id, updated_hunk)
    hunk_doc = txn.fetch(Hunk, hunk_id)
    hunk = hunk_doc.model
    hunk.lines = [line.model for line in all_lines if line.model.hunk_id == hunk_id]
    return UpdateHunkResponse(hunk=hunk)


@ROUTER.delete("/diffs/{diff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diff(diff_id: PrefixedULID, txn: TransactionDependency) -> None:
    diff_doc = txn.get(Diff, diff_id)
    if not diff_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found"
        )
    all_hunks = txn.all(Hunk)
    hunk_ids = [h.model_id for h in all_hunks if h.model.diff_id == diff_id]
    all_lines = txn.all(Line)
    line_ids = [
        line.model_id
        for line in all_lines
        if any(line.model.hunk_id == hunk_id for hunk_id in hunk_ids)
    ]
    all_comments = txn.all(Comment)
    comment_ids = [c.model_id for c in all_comments if c.model.diff_id == diff_id]
    txn.delete_many(Line, line_ids)
    txn.delete_many(Hunk, hunk_ids)
    txn.delete_many(Comment, comment_ids)
    txn.delete(Diff, diff_id)


if __TRYKE_TESTING__:
    from tryke import expect, test

    from diffswarm.app._testing import _client
    from diffswarm.app.models import DiffBase

    PREFIXED_ULID_LENGTH = 28  # prefix + hyphen + 26 character ULID

    @test(name="get diff with invalid id")
    def test_get_diff_invalid_id() -> None:
        with _client() as client:
            res = client.get("/api/diffs/12345")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            )

    @test(name="get diff not found api")
    def test_get_diff_not_found_api() -> None:
        with _client() as client:
            res = client.get(f"/api/diffs/{generate_prefixed_ulid('d')}")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="create and get diff api")
    def test_create_get_diff_api() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get status").to_equal(status.HTTP_200_OK)
            body = res.json()
            diff = body["diff"]
            expect(diff["id"], name="diff id").to_equal(diff_id)
            expect(diff["raw"], name="diff raw").to_equal(DiffBase.HELLO_WORLD)
            expect(diff["from_filename"], name="from filename").to_equal("/dev/fd/14")
            expect(diff["to_filename"], name="to filename").to_equal("/dev/fd/16")
            expect(diff["description"], name="description").to_be_none()
            expect(diff["hunks"], name="hunks count").to_have_length(1)

            hunk = diff["hunks"][0]
            expected_to_count = 2
            expected_line_count = 2
            expected_new_line_number = 2

            expect(hunk["from_start"], name="hunk from_start").to_equal(1)
            expect(hunk["from_count"], name="hunk from_count").to_equal(1)
            expect(hunk["to_start"], name="hunk to_start").to_equal(1)
            expect(hunk["to_count"], name="hunk to_count").to_equal(expected_to_count)
            expect(hunk["lines"], name="hunk lines count").to_have_length(
                expected_line_count
            )

            lines = hunk["lines"]
            expect(lines[0]["type"], name="line 0 type").to_equal("CONTEXT")
            expect(lines[0]["content"], name="line 0 content").to_equal("hello")
            expect(lines[0]["line_number_old"], name="line 0 old line number").to_equal(
                1
            )
            expect(lines[0]["line_number_new"], name="line 0 new line number").to_equal(
                1
            )

            expect(lines[1]["type"], name="line 1 type").to_equal("ADD")
            expect(lines[1]["content"], name="line 1 content").to_equal("world")
            expect(
                lines[1]["line_number_old"], name="line 1 old line number"
            ).to_be_none()
            expect(lines[1]["line_number_new"], name="line 1 new line number").to_equal(
                expected_new_line_number
            )

            expect("id" in lines[0], name="line 0 has id").to_be_truthy()
            expect("id" in lines[1], name="line 1 has id").to_be_truthy()
            expect(
                lines[0]["id"].startswith("l-"), name="line 0 id prefix"
            ).to_be_truthy()
            expect(
                lines[1]["id"].startswith("l-"), name="line 1 id prefix"
            ).to_be_truthy()
            expect(lines[0]["id"], name="line 0 id length").to_have_length(
                PREFIXED_ULID_LENGTH
            )
            expect(lines[1]["id"], name="line 1 id length").to_have_length(
                PREFIXED_ULID_LENGTH
            )

    @test(name="database storage and retrieval")
    def test_database_storage_and_retrieval() -> None:
        with _client() as client:
            expected_to_count = 2
            expected_line_count = 2
            expected_add_line_number = 2
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get status").to_equal(status.HTTP_200_OK)
            body = res.json()
            diff = body["diff"]
            expect(diff["id"], name="diff id").to_equal(diff_id)
            expect(diff["raw"], name="diff raw").to_equal(DiffBase.HELLO_WORLD)
            expect(diff["from_filename"], name="from filename").to_equal("/dev/fd/14")
            expect(diff["to_filename"], name="to filename").to_equal("/dev/fd/16")
            expect(diff["from_timestamp"], name="from timestamp").to_be_truthy()
            expect(diff["to_timestamp"], name="to timestamp").to_be_truthy()
            expect(diff["hunks"], name="hunks count").to_have_length(1)
            hunk = diff["hunks"][0]
            expect(hunk["from_start"], name="hunk from_start").to_equal(1)
            expect(hunk["from_count"], name="hunk from_count").to_equal(1)
            expect(hunk["to_start"], name="hunk to_start").to_equal(1)
            expect(hunk["to_count"], name="hunk to_count").to_equal(expected_to_count)
            lines = hunk["lines"]
            expect(lines, name="lines count").to_have_length(expected_line_count)
            context_line = next(line for line in lines if line["type"] == "CONTEXT")
            expect(context_line["content"], name="context line content").to_equal(
                "hello"
            )
            expect(
                context_line["line_number_old"], name="context old line number"
            ).to_equal(1)
            expect(
                context_line["line_number_new"], name="context new line number"
            ).to_equal(1)
            add_line = next(line for line in lines if line["type"] == "ADD")
            expect(add_line["content"], name="add line content").to_equal("world")
            expect(add_line["line_number_old"], name="add old line number").to_be_none()
            expect(add_line["line_number_new"], name="add new line number").to_equal(
                expected_add_line_number
            )

            expect("id" in context_line, name="context line has id").to_be_truthy()
            expect("id" in add_line, name="add line has id").to_be_truthy()
            expect(
                context_line["id"].startswith("l-"), name="context line id prefix"
            ).to_be_truthy()
            expect(
                add_line["id"].startswith("l-"), name="add line id prefix"
            ).to_be_truthy()
            expect(context_line["id"], name="context line id length").to_have_length(
                PREFIXED_ULID_LENGTH
            )
            expect(add_line["id"], name="add line id length").to_have_length(
                PREFIXED_ULID_LENGTH
            )

    @test(name="create comment")
    def test_create_comment() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get diff status").to_equal(status.HTTP_200_OK)
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
            expect(res.status_code, name="create comment status").to_equal(
                status.HTTP_200_OK
            )
            body = res.json()
            comment = body["comment"]
            expect(comment["text"], name="comment text").to_equal(
                "This is a test comment"
            )
            expect(comment["author"], name="comment author").to_equal("test_user")
            expect(comment["diff_id"], name="comment diff_id").to_equal(diff_id)
            expect(comment["line_index"], name="comment line_index").to_equal(0)
            expect(comment["start_offset"], name="comment start_offset").to_equal(0)
            expected_end_offset = 5
            expect(comment["end_offset"], name="comment end_offset").to_equal(
                expected_end_offset
            )
            expect(comment["in_reply_to"], name="comment in_reply_to").to_be_none()
            expect("id" in comment, name="comment has id").to_be_truthy()
            expect("timestamp" in comment, name="comment has timestamp").to_be_truthy()

    @test(name="delete comment")
    def test_delete_comment() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
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
            expect(res.status_code, name="create comment status").to_equal(
                status.HTTP_200_OK
            )
            comment_id = res.json()["comment"]["id"]
            res = client.delete(f"/api/comments/{comment_id}")
            expect(res.status_code, name="delete status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.delete(f"/api/comments/{comment_id}")
            expect(res.status_code, name="delete again status").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="delete comment not found")
    def test_delete_comment_not_found() -> None:
        with _client() as client:
            res = client.delete(f"/api/comments/{generate_prefixed_ulid('d')}")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Comment not found")

    @test(name="update comment")
    def test_update_comment() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            diff = res.json()["diff"]
            hunk_id = diff["hunks"][0]["id"]

            comment_data = {
                "text": "Original comment text",
                "author": "test_user",
                "hunk_id": str(hunk_id),
                "diff_id": diff_id,
                "line_index": 0,
                "start_offset": 0,
                "end_offset": 5,
            }
            res = client.post("/api/comments", json=comment_data)
            expect(res.status_code, name="create comment status").to_equal(
                status.HTTP_200_OK
            )
            comment_id = res.json()["comment"]["id"]
            original_timestamp = res.json()["comment"]["timestamp"]

            update_data = {"text": "Updated comment text"}
            res = client.put(f"/api/comments/{comment_id}", json=update_data)
            expect(res.status_code, name="update status").to_equal(status.HTTP_200_OK)

            body = res.json()
            comment = body["comment"]
            expect(comment["text"], name="updated text").to_equal(
                "Updated comment text"
            )
            expect(comment["author"], name="author unchanged").to_equal("test_user")
            expect(comment["id"], name="id unchanged").to_equal(comment_id)
            expect(comment["timestamp"], name="timestamp unchanged").to_equal(
                original_timestamp
            )
            expect(comment["diff_id"], name="diff_id unchanged").to_equal(diff_id)
            expect(comment["line_index"], name="line_index unchanged").to_equal(0)
            expect(comment["start_offset"], name="start_offset unchanged").to_equal(0)
            expected_end_offset = 5
            expect(comment["end_offset"], name="end_offset unchanged").to_equal(
                expected_end_offset
            )

    @test(name="update comment not found")
    def test_update_comment_not_found() -> None:
        with _client() as client:
            update_data = {"text": "Updated text"}
            res = client.put(
                f"/api/comments/{generate_prefixed_ulid('c')}", json=update_data
            )
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Comment not found")

    @test(name="create reply comment")
    def test_create_reply_comment() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
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
            expect(res.status_code, name="create parent status").to_equal(
                status.HTTP_200_OK
            )
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
            expect(res.status_code, name="create reply status").to_equal(
                status.HTTP_200_OK
            )

            reply_comment = res.json()["comment"]
            expect(reply_comment["text"], name="reply text").to_equal("Reply comment")
            expect(reply_comment["author"], name="reply author").to_equal("reply_user")
            expect(reply_comment["in_reply_to"], name="in_reply_to").to_equal(
                parent_comment_id
            )

            reply_comment_id = reply_comment["id"]
            res = client.delete(f"/api/comments/{reply_comment_id}")
            expect(res.status_code, name="delete reply status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.delete(f"/api/comments/{parent_comment_id}")
            expect(res.status_code, name="delete parent status").to_equal(
                status.HTTP_204_NO_CONTENT
            )

    @test(name="update diff name")
    def test_update_diff_name() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            update_data = {"name": "My Custom Diff Name"}
            res = client.put(f"/api/diffs/{diff_id}", json=update_data)
            expect(res.status_code, name="update status").to_equal(status.HTTP_200_OK)
            body = res.json()
            diff = body["diff"]
            expect(diff["name"], name="updated name").to_equal("My Custom Diff Name")
            expect(diff["id"], name="diff id").to_equal(diff_id)

    @test(name="update diff not found")
    def test_update_diff_not_found() -> None:
        with _client() as client:
            update_data = {"name": "Test Name"}
            res = client.put(
                f"/api/diffs/{generate_prefixed_ulid('d')}", json=update_data
            )
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Diff not found")

    @test(name="update diff description")
    def test_update_diff_description() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]

            update_data = {"description": "This is a test description"}
            res = client.put(f"/api/diffs/{diff_id}", json=update_data)
            expect(res.status_code, name="set description status").to_equal(
                status.HTTP_200_OK
            )
            body = res.json()
            diff = body["diff"]
            expect(diff["description"], name="set description").to_equal(
                "This is a test description"
            )
            expect(diff["id"], name="diff id").to_equal(diff_id)

            update_data = {"description": "Updated description"}
            res = client.put(f"/api/diffs/{diff_id}", json=update_data)
            expect(res.status_code, name="update description status").to_equal(
                status.HTTP_200_OK
            )
            body = res.json()
            diff = body["diff"]
            expect(diff["description"], name="updated description").to_equal(
                "Updated description"
            )

            update_data = {"description": None}
            res = client.put(f"/api/diffs/{diff_id}", json=update_data)
            expect(res.status_code, name="clear description status").to_equal(
                status.HTTP_200_OK
            )
            body = res.json()
            diff = body["diff"]
            expect(diff["description"], name="cleared description").to_be_none()

    @test(name="update diff name and description")
    def test_update_diff_name_and_description() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]

            update_data = {"name": "Custom Diff", "description": "Custom description"}
            res = client.put(f"/api/diffs/{diff_id}", json=update_data)
            expect(res.status_code, name="update status").to_equal(status.HTTP_200_OK)
            body = res.json()
            diff = body["diff"]
            expect(diff["name"], name="updated name").to_equal("Custom Diff")
            expect(diff["description"], name="updated description").to_equal(
                "Custom description"
            )
            expect(diff["id"], name="diff id").to_equal(diff_id)

    @test(name="update hunk name")
    def test_update_hunk_name() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            diff = res.json()["diff"]
            hunk_id = diff["hunks"][0]["id"]
            update_data = {"name": "My Custom Hunk Name"}
            res = client.put(f"/api/hunks/{hunk_id}", json=update_data)
            expect(res.status_code, name="update status").to_equal(status.HTTP_200_OK)
            body = res.json()
            hunk = body["hunk"]
            expect(hunk["name"], name="updated name").to_equal("My Custom Hunk Name")
            expect(hunk["id"], name="hunk id").to_equal(hunk_id)

    @test(name="update hunk not found")
    def test_update_hunk_not_found() -> None:
        with _client() as client:
            update_data = {"name": "Test Name"}
            res = client.put(
                f"/api/hunks/{generate_prefixed_ulid('h')}", json=update_data
            )
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Hunk not found")

    @test(name="delete diff api")
    def test_delete_diff() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get status").to_equal(status.HTTP_200_OK)
            res = client.delete(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="delete status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get after delete status").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="delete diff not found api")
    def test_delete_diff_not_found() -> None:
        with _client() as client:
            res = client.delete(f"/api/diffs/{generate_prefixed_ulid('d')}")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Diff not found")

    @test(name="cascade delete diff deletes hunks lines and comments")
    def test_cascade_delete_diff_deletes_hunks_lines_comments() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get diff status").to_equal(status.HTTP_200_OK)
            diff = res.json()["diff"]
            hunk_id = diff["hunks"][0]["id"]
            expect(diff["hunks"], name="hunks count").to_have_length(1)
            expected_line_count = 2
            expect(diff["hunks"][0]["lines"], name="lines count").to_have_length(
                expected_line_count
            )
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
            expect(res.status_code, name="create comment 1 status").to_equal(
                status.HTTP_200_OK
            )
            res = client.post("/api/comments", json=comment_data)
            expect(res.status_code, name="create comment 2 status").to_equal(
                status.HTTP_200_OK
            )
            comment_id = res.json()["comment"]["id"]
            res = client.delete(f"/api/comments/{comment_id}")
            expect(res.status_code, name="delete comment status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.post("/api/comments", json=comment_data)
            expect(res.status_code, name="create comment 3 status").to_equal(
                status.HTTP_200_OK
            )
            comment_id_2 = res.json()["comment"]["id"]
            res = client.delete(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="delete diff status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.get(f"/api/diffs/{diff_id}")
            expect(res.status_code, name="get deleted diff status").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            res = client.delete(f"/api/comments/{comment_id_2}")
            expect(res.status_code, name="cascaded comment gone status").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="cascade delete comment deletes replies")
    def test_cascade_delete_comment_deletes_replies() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create diff status").to_equal(
                status.HTTP_201_CREATED
            )
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
            expect(res.status_code, name="create parent status").to_equal(
                status.HTTP_200_OK
            )
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
            expect(res.status_code, name="create reply status").to_equal(
                status.HTTP_200_OK
            )
            reply_comment_id = res.json()["comment"]["id"]
            res = client.delete(f"/api/comments/{parent_comment_id}")
            expect(res.status_code, name="delete parent status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.delete(f"/api/comments/{reply_comment_id}")
            expect(res.status_code, name="cascaded reply gone status").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="toggle hunk completion")
    def test_toggle_hunk_completion() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/api/diffs/{diff_id}")
            diff = res.json()["diff"]
            hunk_id = diff["hunks"][0]["id"]
            expect(
                diff["hunks"][0]["completed_at"], name="initially not completed"
            ).to_be_none()
            completed_at = datetime.now(UTC).isoformat()
            res = client.put(
                f"/api/hunks/{hunk_id}", json={"completed_at": completed_at}
            )
            expect(res.status_code, name="complete status").to_equal(status.HTTP_200_OK)
            hunk = res.json()["hunk"]
            expect(hunk["completed_at"], name="completed_at set").to_be_truthy()
            res = client.put(f"/api/hunks/{hunk_id}", json={"completed_at": None})
            expect(res.status_code, name="uncomplete status").to_equal(
                status.HTTP_200_OK
            )
            hunk = res.json()["hunk"]
            expect(hunk["completed_at"], name="completed_at cleared").to_be_none()

    @test(name="toggle hunk completion not found")
    def test_toggle_hunk_completion_not_found() -> None:
        with _client() as client:
            completed_at = datetime.now(UTC).isoformat()
            res = client.put(
                f"/api/hunks/{generate_prefixed_ulid('h')}",
                json={"completed_at": completed_at},
            )
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )
            body = res.json()
            expect(body["detail"], name="error detail").to_equal("Hunk not found")
