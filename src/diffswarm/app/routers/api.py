from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload
from ulid import ULID

from diffswarm.app.database import DBComment, DBDiff, DBHunk
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import Comment, Diff, DiffSwarmBaseModel, Hunk

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: Diff


class CreateCommentRequest(DiffSwarmBaseModel):
    text: str
    author: str
    hunk_id: ULID
    diff_id: ULID
    line_index: int
    start_offset: int
    end_offset: int
    in_reply_to: ULID | None = None


class CreateCommentResponse(DiffSwarmBaseModel):
    comment: Comment


class UpdateDiffRequest(DiffSwarmBaseModel):
    name: str


class UpdateDiffResponse(DiffSwarmBaseModel):
    diff: Diff


class UpdateHunkRequest(DiffSwarmBaseModel):
    name: str


class UpdateHunkResponse(DiffSwarmBaseModel):
    hunk: Hunk


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: ULID, session: SessionDependency) -> GetDiffResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == str(diff_id))
        .one()
    )
    diff = Diff.from_db(db_diff)
    return GetDiffResponse(diff=diff)


@ROUTER.post("/comments")
def create_comment(
    request: CreateCommentRequest, session: SessionDependency
) -> CreateCommentResponse:
    db_comment = DBComment(
        id=str(ULID()),
        text=request.text,
        author=request.author,
        timestamp=datetime.now(UTC),
        hunk_id=str(request.hunk_id),
        diff_id=str(request.diff_id),
        line_index=request.line_index,
        start_offset=request.start_offset,
        end_offset=request.end_offset,
        in_reply_to=str(request.in_reply_to) if request.in_reply_to else None,
    )
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    comment = Comment.from_db(db_comment)
    return CreateCommentResponse(comment=comment)


@ROUTER.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: ULID, session: SessionDependency) -> None:
    db_comment = (
        session.query(DBComment).filter(DBComment.id == str(comment_id)).first()
    )
    if not db_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    session.delete(db_comment)
    session.commit()


@ROUTER.put("/diffs/{diff_id}")
def update_diff(
    diff_id: ULID, request: UpdateDiffRequest, session: SessionDependency
) -> UpdateDiffResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == str(diff_id))
        .first()
    )
    if not db_diff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found"
        )

    db_diff.name = request.name
    session.commit()
    session.refresh(db_diff)

    diff = Diff.from_db(db_diff)
    return UpdateDiffResponse(diff=diff)


@ROUTER.put("/hunks/{hunk_id}")
def update_hunk(
    hunk_id: ULID, request: UpdateHunkRequest, session: SessionDependency
) -> UpdateHunkResponse:
    db_hunk = (
        session.query(DBHunk)
        .options(selectinload(DBHunk.lines))
        .filter(DBHunk.id == str(hunk_id))
        .first()
    )
    if not db_hunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Hunk not found"
        )

    db_hunk.name = request.name
    session.commit()
    session.refresh(db_hunk)

    hunk = Hunk.from_db(db_hunk)
    return UpdateHunkResponse(hunk=hunk)


@ROUTER.delete("/diffs/{diff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diff(diff_id: ULID, session: SessionDependency) -> None:
    db_diff = session.query(DBDiff).filter(DBDiff.id == str(diff_id)).first()
    if not db_diff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found"
        )
    session.delete(db_diff)
    session.commit()
