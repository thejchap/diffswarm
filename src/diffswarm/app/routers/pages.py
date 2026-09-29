from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BeforeValidator
from starlette.status import HTTP_201_CREATED, HTTP_204_NO_CONTENT
from tryke_guard import __TRYKE_TESTING__

from diffswarm.app.dependencies import (
    DatabaseDependency,
    SettingsDependency,
    TransactionDependency,
)
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
    database: DatabaseDependency,
    settings: SettingsDependency,
) -> HTMLResponse:
    experimental = "experimental-pierre-rendering" in request.query_params
    with database.read_transaction() as txn:
        if experimental:
            diff = txn.fetch(Diff, diff_id).model
            comments = []
        else:
            diff = load_diff_with_relations(txn, diff_id)
            comments = txn.comments_for_diff(diff_id)
    comments.sort(key=lambda c: c.timestamp)
    return TEMPLATES.TemplateResponse(
        request=request,
        name="pages/pierre.html" if experimental else "pages/diff.html",
        context={
            "diff": diff,
            "comments": comments,
            "git_hash": settings.git_hash,
            "normal_view_url": str(
                request.url.remove_query_params("experimental-pierre-rendering")
            ),
        },
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


if __TRYKE_TESTING__:
    from starlette import status
    from tryke import expect, test

    from diffswarm.app._testing import _client

    @test(name="get home page")
    def test_get_home() -> None:
        with _client() as client:
            res = client.get("/")
            expect(res.status_code, name="status code").to_equal(status.HTTP_200_OK)
            expect(res.text, name="body contains diffswarm").to_contain("diffswarm")
            expect(res.text, name="body contains html tag").to_contain("<html")

    @test(name="get diff not found page")
    def test_get_diff_not_found_pages() -> None:
        with _client() as client:
            res = client.get(f"/diffs/{generate_prefixed_ulid('d')}")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="create and get diff page")
    def test_create_get_diff_pages() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/{diff_id}")
            expect(res.status_code, name="get status").to_equal(status.HTTP_200_OK)
            body = res.text
            expect(body, name="body contains html tag").to_contain("<html")

    @test(name="delete diff page")
    def test_delete_diff_pages() -> None:
        with _client() as client:
            res = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            expect(res.status_code, name="create status").to_equal(
                status.HTTP_201_CREATED
            )
            diff_id = res.headers["X-Diff-ID"]
            res = client.get(f"/{diff_id}")
            expect(res.status_code, name="get status").to_equal(status.HTTP_200_OK)
            res = client.delete(f"/{diff_id}")
            expect(res.status_code, name="delete status").to_equal(
                status.HTTP_204_NO_CONTENT
            )
            res = client.get(f"/{diff_id}")
            expect(res.status_code, name="get after delete status").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="delete diff not found page")
    def test_delete_diff_not_found_pages() -> None:
        with _client() as client:
            res = client.delete(f"/{generate_prefixed_ulid('d')}")
            expect(res.status_code, name="status code").to_equal(
                status.HTTP_404_NOT_FOUND
            )

    @test(name="query flag selects Pierre while ordinary pages keep the normal viewer")
    def test_pierre_page_selection() -> None:
        import re  # noqa: PLC0415
        from html import unescape  # noqa: PLC0415

        with _client() as client:
            response = client.post(
                "/",
                content=DiffBase.HELLO_WORLD,
                headers={"Content-Type": "text/plain"},
            )
            diff_id = response.headers["X-Diff-ID"]
            original = client.get(f"/api/diffs/{diff_id}").json()
            for query in ("", "?search=hello", "?other-flag"):
                response = client.get(f"/{diff_id}{query}")
                expect(response.status_code).to_equal(status.HTTP_200_OK)
                expect(response.text).to_contain("/static/js/diff.js?")
                expect(response.text).to_contain("data-comments-prefetch=")
                expect('id="pierre-viewer"' in response.text).to_be_falsy()
            for query in (
                "?experimental-pierre-rendering",
                "?experimental-pierre-rendering=1",
                "?experimental-pierre-rendering=false&search=hello",
            ):
                response = client.get(f"/{diff_id}{query}")
                expect(response.status_code).to_equal(status.HTTP_200_OK)
                expect(response.text).to_contain("/static/js/pierre.js?")
                expect("data-comments-prefetch=" in response.text).to_be_falsy()
                expect("data-diff-prefetch=" in response.text).to_be_falsy()
                patch_match = re.search(r'data-patch="([^"]*)"', response.text)
                assert patch_match is not None  # noqa: S101
                expect(unescape(patch_match.group(1))).to_equal(DiffBase.HELLO_WORLD)
            expect(response.text).to_contain(f"/{diff_id}?search=hello")
            expect(client.get(f"/api/diffs/{diff_id}").json()).to_equal(original)

    @test(name="experimental page escapes patch text and returns 404 for missing diffs")
    def test_pierre_page_content() -> None:
        with _client() as client:
            raw = (
                '--- old.html\n+++ new.html\n@@ -1 +1 @@\n-old\n+<script>"&"</script>\n'
            )
            response = client.post(
                "/",
                content=raw,
                headers={"Content-Type": "text/plain"},
            )
            diff_id = response.headers["X-Diff-ID"]
            response = client.get(f"/{diff_id}?experimental-pierre-rendering")
            expect(response.status_code).to_equal(status.HTTP_200_OK)
            expect(response.text).to_contain("&lt;script&gt;")
            expect('<script>"&"</script>' in response.text).to_be_falsy()
            response = client.get(
                f"/{generate_prefixed_ulid('d')}?experimental-pierre-rendering"
            )
            expect(response.status_code).to_equal(status.HTTP_404_NOT_FOUND)
