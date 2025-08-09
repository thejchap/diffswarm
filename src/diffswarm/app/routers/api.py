from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload
from ulid import ULID

from diffswarm.app.database import DBComment, DBDiff, DBHunk
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import Comment, Diff, DiffSwarmBaseModel

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: Diff


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


class GetCommentsResponse(DiffSwarmBaseModel):
    comments: list[Comment]


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


@ROUTER.get("/diffs/{diff_id}/comments")
def get_comments_for_diff(
    diff_id: ULID, session: SessionDependency
) -> GetCommentsResponse:
    db_comments = (
        session.query(DBComment)
        .filter(DBComment.diff_id == str(diff_id))
        .order_by(DBComment.timestamp)
        .all()
    )
    comments = [Comment.from_db(db_comment) for db_comment in db_comments]
    return GetCommentsResponse(comments=comments)


@ROUTER.get("/hunks/{hunk_id}/comments")
def get_comments_for_hunk(
    hunk_id: ULID, session: SessionDependency
) -> GetCommentsResponse:
    db_comments = (
        session.query(DBComment)
        .filter(DBComment.hunk_id == str(hunk_id))
        .order_by(DBComment.timestamp)
        .all()
    )
    comments = [Comment.from_db(db_comment) for db_comment in db_comments]
    return GetCommentsResponse(comments=comments)


@ROUTER.delete("/comments/{comment_id}")
def delete_comment(comment_id: ULID, session: SessionDependency) -> dict[str, str]:
    db_comment = (
        session.query(DBComment).filter(DBComment.id == str(comment_id)).first()
    )
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    session.delete(db_comment)
    session.commit()
    return {"message": "Comment deleted successfully"}
