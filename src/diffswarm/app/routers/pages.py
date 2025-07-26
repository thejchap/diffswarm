from typing import Annotated

from fastapi import APIRouter, Body, Request
from fastapi.responses import PlainTextResponse
from pydantic import BeforeValidator
from ulid import ULID

from diffswarm.app.models import Diff

ROUTER = APIRouter()


@ROUTER.get("/", response_class=PlainTextResponse)
def home():
    return "diffswarm"


@ROUTER.get("/diffs/{diff_id}", response_class=PlainTextResponse)
def get_diff(diff_id: ULID):
    return f"diffswarm {diff_id}"


@ROUTER.post(
    "/",
    response_class=PlainTextResponse,
    description="""\
Create a new diff from a unified diff string

# Example
```sh
diff <(echo "hello") <(echo "hello\nworld") -u | \
curl  --header 'Content-Type: text/plain'  -X POST --data-binary @- localhost:8000
```
""".strip(),
)
def create_diff(
    req: Request,
    body: Annotated[
        Diff,
        BeforeValidator(Diff.parse, json_schema_input_type=str),
        Body(examples=[Diff.HELLO_WORLD], media_type="text/plain"),
    ],
):
    return f"{req.url_for('get_diff', diff_id=ULID())}\n"
