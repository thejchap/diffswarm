from typing import Annotated

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from starlette.status import HTTP_201_CREATED
from ulid import ULID

from diffswarm.app.database import DBDiff
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import DiffBase
from diffswarm.app.templates import TEMPLATES

ROUTER = APIRouter()


@ROUTER.get("/", response_class=PlainTextResponse)
def home() -> str:
    return "diffswarm"


@ROUTER.get("/diffs/{_diff_id}", response_class=HTMLResponse)
def get_diff(
    request: Request,
    _diff_id: ULID,
    _session: SessionDependency,
) -> HTMLResponse:
    diff = DiffBase.parse_str(DiffBase.HELLO_WORLD)
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
    db_diff = DBDiff(id=str(ULID()), raw=body.raw)
    session.add(db_diff)
    session.commit()
    session.refresh(db_diff)
    res.headers["X-Diff-ID"] = db_diff.id
    return f"{req.url_for('get_diff', _diff_id=db_diff.id)}\n"
