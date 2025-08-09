from typing import Annotated

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from sqlalchemy.orm import selectinload
from starlette.status import HTTP_201_CREATED
from ulid import ULID

from diffswarm.app.database import DBDiff, DBHunk, DBLine
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import Diff, DiffBase
from diffswarm.app.templates import TEMPLATES

ROUTER = APIRouter()


@ROUTER.get("/", response_class=PlainTextResponse)
def home() -> str:
    return "diffswarm"


@ROUTER.get("/diffs/{diff_id}", response_class=HTMLResponse)
def get_diff(
    request: Request,
    diff_id: ULID,
    session: SessionDependency,
) -> HTMLResponse:
    db_diff = (
        session.query(DBDiff)
        .options(selectinload(DBDiff.hunks).selectinload(DBHunk.lines))
        .filter(DBDiff.id == str(diff_id))
        .one()
    )
    diff = Diff.from_db(db_diff)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/diffs/[diff_id]/index.html",
        context={"diff": diff},
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
    db_diff = DBDiff(
        id=str(ULID()),
        raw=body.raw,
        from_filename=body.from_filename,
        from_timestamp=body.from_timestamp.isoformat() if body.from_timestamp else None,
        to_filename=body.to_filename,
        to_timestamp=body.to_timestamp.isoformat() if body.to_timestamp else None,
    )
    session.add(db_diff)
    session.flush()  # Flush to get the ID assigned

    # Create hunks and lines
    for hunk_data in body.hunks:
        db_hunk = DBHunk(
            id=str(ULID()),
            diff_id=db_diff.id,
            from_start=hunk_data.from_start,
            from_count=hunk_data.from_count,
            to_start=hunk_data.to_start,
            to_count=hunk_data.to_count,
        )
        session.add(db_hunk)
        session.flush()  # Flush to get the hunk ID

        for line_data in hunk_data.lines:
            db_line = DBLine(
                id=str(ULID()),
                hunk_id=db_hunk.id,
                type=line_data.type.value,
                content=line_data.content,
                line_number_old=line_data.line_number_old,
                line_number_new=line_data.line_number_new,
            )
            session.add(db_line)

    session.commit()
    session.refresh(db_diff)
    res.headers["X-Diff-ID"] = db_diff.id
    return f"{req.url_for('get_diff', diff_id=db_diff.id)}\n"
