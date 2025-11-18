from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT

from diffswarm.app.dependencies import SettingsDependency
from diffswarm.app.models import (
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
    settings: SettingsDependency,
) -> HTMLResponse:
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/diff.html",
        context={"diff": None, "comments": [], "git_hash": settings.git_hash},
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
) -> str:
    diff_id = generate_prefixed_ulid("d")
    res.headers["X-Diff-ID"] = diff_id
    return f"{req.url_for('get_diff', diff_id=diff_id)}\n"


@ROUTER.delete("/{diff_id}", status_code=HTTP_204_NO_CONTENT)
def delete_diff(diff_id: PrefixedULID) -> None:
    raise HTTPException(status_code=404, detail="Diff not found")
