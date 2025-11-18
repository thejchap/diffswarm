from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from diffswarm.app.models import (
    Comment,
    Diff,
    DiffSwarmBaseModel,
    Hunk,
    PrefixedULID,
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


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: PrefixedULID) -> GetDiffResponse:
    diff = Diff(
        id="test",
        name="test",
        raw="test",
        from_filename="test",
        to_filename="test",
        hunks=[],
    )
    return GetDiffResponse(diff=diff)


@ROUTER.post("/comments")
def create_comment(request: CreateCommentRequest) -> CreateCommentResponse:
    comment = Comment(
        id="test",
        text="text",
        author="anonymous",
        timestamp=datetime.now(),
        hunk_id="123",
        diff_id="123",
        line_index=1,
        start_offset=1,
        end_offset=1,
    )
    return CreateCommentResponse(comment=comment)


@ROUTER.put("/comments/{comment_id}")
def update_comment(
    comment_id: PrefixedULID, request: UpdateCommentRequest
) -> UpdateCommentResponse:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
    )


@ROUTER.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: PrefixedULID) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
    )


@ROUTER.put("/diffs/{diff_id}")
def update_diff(
    diff_id: PrefixedULID, request: UpdateDiffRequest
) -> UpdateDiffResponse:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found")


@ROUTER.put("/hunks/{hunk_id}")
def update_hunk(
    hunk_id: PrefixedULID, request: UpdateHunkRequest
) -> UpdateHunkResponse:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hunk not found")


@ROUTER.delete("/diffs/{diff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diff(diff_id: PrefixedULID) -> None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found")
