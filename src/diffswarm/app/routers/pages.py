from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from diffswarm.app.dependencies import TransactionDependency
from diffswarm.app.models import (
    Comment,
    Diff,
    DiffBase,
    Hunk,
    Line,
    PrefixedULID,
    generate_prefixed_ulid,
)
from diffswarm.app.routers.api import load_diff_with_relations
from diffswarm.app.templates import TEMPLATES

ROUTER = APIRouter()


@ROUTER.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    url = str(request.url_for("home")).rstrip("/")
    snippet = f"""\
diff <(echo "foo") <(echo "foo\\nbar") -u | curl -X POST --data-binary @- {url}
    """.strip()
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/index.html",
        context={"snippet": snippet},
    )


@ROUTER.get("/{diff_id}", response_class=HTMLResponse)
def get_diff(
    request: Request,
    diff_id: PrefixedULID,
    txn: TransactionDependency,
) -> HTMLResponse:
    diff = load_diff_with_relations(txn, diff_id)
    all_comments = txn.all(Comment)
    comments = [c.model for c in all_comments if c.model.diff_id == diff_id]
    comments.sort(key=lambda c: c.timestamp)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/diff.html",
        context={"diff": diff, "comments": comments},
    )


@ROUTER.post("/", response_class=PlainTextResponse, status_code=HTTP_201_CREATED)
def create_diff(
    req: Request,
    res: Response,
    body: Annotated[
        DiffBase,
        BeforeValidator(DiffBase.parse_bytes, json_schema_input_type=str),
        Body(examples=[DiffBase.HELLO_WORLD], media_type="text/plain"),
    ],
    txn: TransactionDependency,
) -> str:
    diff_id = generate_prefixed_ulid("d")
    hunks: list[Hunk] = []
    for hunk_data in body.hunks:
        hunk_id = generate_prefixed_ulid("h")
        lines: list[Line] = []
        for line_data in hunk_data.lines:
            line_id = generate_prefixed_ulid("l")
            line = Line(
                id=line_id,
                hunk_id=hunk_id,
                type=line_data.type,
                content=line_data.content,
                line_number_old=line_data.line_number_old,
                line_number_new=line_data.line_number_new,
            )
            lines.append(line)
            txn.put(Line, line_id, line)
        hunk = Hunk(
            id=hunk_id,
            diff_id=diff_id,
            name=hunk_id,
            from_start=hunk_data.from_start,
            from_count=hunk_data.from_count,
            to_start=hunk_data.to_start,
            to_count=hunk_data.to_count,
            completed_at=None,
            lines=[],
        )
        hunks.append(hunk)
        txn.put(Hunk, hunk_id, hunk)
    diff = Diff(
        id=diff_id,
        name=diff_id,
        raw=body.raw,
        from_filename=body.from_filename,
        from_timestamp=body.from_timestamp,
        to_filename=body.to_filename,
        to_timestamp=body.to_timestamp,
        description=None,
        hunks=[],
    )
    txn.put(Diff, diff_id, diff)
    res.headers["X-Diff-ID"] = diff_id
    return f"{req.url_for('get_diff', diff_id=diff_id)}\n"


@ROUTER.delete("/{diff_id}", status_code=HTTP_204_NO_CONTENT)
def delete_diff(diff_id: PrefixedULID, txn: TransactionDependency) -> None:
    diff_doc = txn.get(Diff, diff_id)
    if not diff_doc:
        raise HTTPException(status_code=404, detail="Diff not found")
    all_hunks = txn.all(Hunk)
    hunk_ids = [h.model_id for h in all_hunks if h.model.diff_id == diff_id]
    all_lines = txn.all(Line)
    for hunk_id in hunk_ids:
        line_ids = [
            line.model_id for line in all_lines if line.model.hunk_id == hunk_id
        ]
        for line_id in line_ids:
            txn.delete(Line, line_id)
        txn.delete(Hunk, hunk_id)
    all_comments = txn.all(Comment)
    comment_ids = [c.model_id for c in all_comments if c.model.diff_id == diff_id]
    for comment_id in comment_ids:
        txn.delete(Comment, comment_id)
    txn.delete(Diff, diff_id)
