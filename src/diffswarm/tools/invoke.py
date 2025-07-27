import inspect
import json
import sys
from typing import Any

from fastapi.params import Body
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from typing_extensions import _AnnotatedAlias  # type:ignore[reportPrivateUsage]

from diffswarm.app import APP


def invoke() -> str:
    """Stateless request to an API endpoint, by name or qualified name."""
    route_name = sys.argv[1]
    route = next(
        r
        for r in APP.routes
        if isinstance(r, APIRoute) and (route_name in (r.name, r.endpoint.__qualname__))
    )
    sig = inspect.signature(route.endpoint)
    body_example: str | dict[str, Any] | None = None
    if body := sig.parameters.get("body"):
        annotation = body.annotation
        if (
            isinstance(annotation, _AnnotatedAlias)
            and (
                body_meta := next(
                    (m for m in annotation.__metadata__ if isinstance(m, Body)),
                    None,
                )
            )
            and (examples := body_meta.examples)
        ):
            body_example = examples[0]
    with TestClient(APP, base_url="http://localhost:8000") as client:
        response = client.request(
            method=route.methods.pop(),
            url=route.path,
            headers={
                "Content-Type": "application/json"
                if isinstance(body_example, dict)
                else "text/plain"
            },
            content=body_example.encode("utf-8")
            if body_example and isinstance(body_example, str)
            else None,
            json=body_example
            if body_example and isinstance(body_example, dict)
            else None,
        )
    if response.headers.get("content-type") == "application/json":
        return json.dumps(response.json(), indent=4)
    return response.text


if __name__ == "__main__":
    print(invoke())  # noqa: T201
