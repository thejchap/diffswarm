# d-01arz3ndektsv4rrffq69g5fav

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from diffswarm.app.database import DBComment, DBDiff, DBHunk
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import (
    Comment,
    Diff,
    DiffSwarmBaseModel,
    Hunk,
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

    def to_db(self) -> DBComment:
        return DBComment(
            id=generate_prefixed_ulid("c"),
            text=self.text,
            author=self.author,
            timestamp=datetime.now(UTC),
            hunk_id=self.hunk_id,
            diff_id=self.diff_id,
            line_index=self.line_index,
            start_offset=self.start_offset,
            end_offset=self.end_offset,
            in_reply_to=self.in_reply_to if self.in_reply_to else None,
        )


class CreateCommentResponse(DiffSwarmBaseModel):
    comment: Comment


class UpdateDiffRequest(DiffSwarmBaseModel):
    name: str


class UpdateDiffResponse(DiffSwarmBaseModel):
    diff: Diff


class UpdateHunkRequest(DiffSwarmBaseModel):
    name: str | None = None
    completed_at: datetime | None = None


class UpdateHunkResponse(DiffSwarmBaseModel):
    hunk: Hunk


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: PrefixedULID, session: SessionDependency) -> GetDiffResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == diff_id)
        .one()
    )
    diff = Diff.from_db(db_diff)
    return GetDiffResponse(diff=diff)


@ROUTER.post("/comments")
def create_comment(
    request: CreateCommentRequest, session: SessionDependency
) -> CreateCommentResponse:
    db_comment = request.to_db()
    session.add(db_comment)
    session.commit()
    session.refresh(db_comment)
    comment = Comment.from_db(db_comment)
    return CreateCommentResponse(comment=comment)


@ROUTER.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: PrefixedULID, session: SessionDependency) -> None:
    db_comment = session.query(DBComment).filter(DBComment.id == comment_id).first()
    if not db_comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
        )
    session.delete(db_comment)
    session.commit()


@ROUTER.put("/diffs/{diff_id}")
def update_diff(
    diff_id: PrefixedULID, request: UpdateDiffRequest, session: SessionDependency
) -> UpdateDiffResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == diff_id)
        .with_for_update()
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
    hunk_id: PrefixedULID, request: UpdateHunkRequest, session: SessionDependency
) -> UpdateHunkResponse:
    db_hunk = (
        session.query(DBHunk)
        .options(selectinload(DBHunk.lines))
        .filter(DBHunk.id == hunk_id)
        .with_for_update()
        .first()
    )
    if not db_hunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Hunk not found"
        )

    # Update fields if provided
    if request.name is not None:
        db_hunk.name = request.name
    if "completed_at" in request.model_fields_set:
        db_hunk.completed_at = request.completed_at

    session.commit()
    session.refresh(db_hunk)

    hunk = Hunk.from_db(db_hunk)
    return UpdateHunkResponse(hunk=hunk)


@ROUTER.delete("/diffs/{diff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diff(diff_id: PrefixedULID, session: SessionDependency) -> None:
    db_diff = session.query(DBDiff).filter(DBDiff.id == diff_id).first()
    if not db_diff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Diff not found"
        )
    session.delete(db_diff)
    session.commit()
