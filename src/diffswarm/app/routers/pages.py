from typing import Annotated

from fastapi import APIRouter, Body, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from ulid import ULID

from diffswarm.app.database import DBDiff
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
    diff = Diff.model_validate(
        session.query(DBDiff.id, DBDiff.raw).filter(DBDiff.id == str(diff_id)).one()
    )
    return TEMPLATES.TemplateResponse(
        request=request, name="diff.html", context={"diff": diff}
    )


@ROUTER.post(
    "/",
    response_class=PlainTextResponse,
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
    body: Annotated[
        DiffBase,
        BeforeValidator(DiffBase.parse_bytes, json_schema_input_type=str),
        Body(examples=[DiffBase.HELLO_WORLD], media_type="text/plain"),
    ],
    session: SessionDependency,
) -> str:
    db_diff = DBDiff(id=str(ULID()), raw=body.raw)
    session.add(db_diff)
    session.commit()
    session.refresh(db_diff)
    return f"{req.url_for('get_diff', diff_id=db_diff.id)}\n"
