from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sapling.errors import NotFoundError

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
