from typing import Annotated

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_201_CREATED

from diffswarm.app.database import DBComment, DBDiff, DBHunk, DBLine
from diffswarm.app.dependencies import SessionDependency, SettingsDependency
from diffswarm.app.models import (
    Comment,
    Diff,
    DiffBase,
    PrefixedULID,
    generate_prefixed_ulid,
)
from diffswarm.app.templates import TEMPLATES

ROUTER = APIRouter()


@ROUTER.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    url = str(request.url_for("home")).rstrip("/")
    snippet = f"""\
diff <(echo "hello") <(echo "hello\\nworld") -u | curl --header 'Content-Type: text/plain' -X POST --data-binary @- {url}
    """.strip()  # noqa: E501
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={"snippet": snippet},
    )


@ROUTER.get("/{diff_id}", response_class=HTMLResponse)
def get_diff(
    request: Request,
    diff_id: PrefixedULID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> HTMLResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == diff_id)
        .one()
    )
    diff = Diff.from_db(db_diff)

    # Fetch comments for this diff
    db_comments = (
        session.query(DBComment)
        .filter(DBComment.diff_id == diff_id)
        .order_by(DBComment.timestamp)
        .all()
    )
    comments = [Comment.from_db(db_comment) for db_comment in db_comments]

    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/diff.html",
        context={"diff": diff, "comments": comments, "git_hash": settings.git_hash},
    )


@ROUTER.post(
    "/",
    response_class=PlainTextResponse,
    status_code=HTTP_201_CREATED,
    description="""\
Create a new diff from a unified diff string

# Example
```sh
diff <(echo "hello") <(echo "hello\nworld") -u | \
curl --header 'Content-Type: text/plain' -X POST --data-binary @- localhost:8000
```
""".strip(),
)
def create_diff(
    req: Request,
    res: Response,
    body: Annotated[
        DiffBase,
        BeforeValidator(DiffBase.parse_bytes, json_schema_input_type=str),
        Body(examples=[DiffBase.HELLO_WORLD], media_type="text/plain"),
    ],
    session: SessionDependency,
) -> str:
    diff_id = generate_prefixed_ulid("d")
    db_diff = DBDiff(
        id=diff_id,
        name=diff_id,
        raw=body.raw,
        from_filename=body.from_filename,
        from_timestamp=body.from_timestamp.isoformat() if body.from_timestamp else None,
        to_filename=body.to_filename,
        to_timestamp=body.to_timestamp.isoformat() if body.to_timestamp else None,
    )
    session.add(db_diff)
    for hunk_data in body.hunks:
        hunk_id = generate_prefixed_ulid("h")
        db_hunk = DBHunk(
            id=hunk_id,
            name=hunk_id,
            diff_id=diff_id,
            from_start=hunk_data.from_start,
            from_count=hunk_data.from_count,
            to_start=hunk_data.to_start,
            to_count=hunk_data.to_count,
        )
        session.add(db_hunk)
        for line_data in hunk_data.lines:
            db_line = DBLine(
                id=generate_prefixed_ulid("l"),
                hunk_id=hunk_id,
                type=line_data.type.value,
                content=line_data.content,
                line_number_old=line_data.line_number_old,
                line_number_new=line_data.line_number_new,
            )
            session.add(db_line)
    session.commit()
    res.headers["X-Diff-ID"] = diff_id
    return f"{req.url_for('get_diff', diff_id=diff_id)}\n"
