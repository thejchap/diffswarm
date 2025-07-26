import inspect
import json
import sys

from fastapi.params import Body
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from typing_extensions import _AnnotatedAlias

from diffswarm.app import APP


def invoke():
    """
    Stateless request to an API endpoint, by name or qualified name.
    """
    route_name = sys.argv[1]
    route = next(
        r
        for r in APP.routes
        if isinstance(r, APIRoute)
        and (r.name == route_name or r.endpoint.__qualname__ == route_name)
    )
    sig = inspect.signature(route.endpoint)
    body_example = None
    if body := sig.parameters.get("body"):
        annotation = body.annotation
        if isinstance(annotation, _AnnotatedAlias):
            if body_meta := next(
                (m for m in annotation.__metadata__ if isinstance(m, Body)),
                None,
            ):
                if examples := body_meta.examples:
                    body_example = examples[0]
    with TestClient(APP, base_url="http://localhost:8000") as client:
        response = client.request(
            method=route.methods.pop(),
            url=route.path,
            json=body_example,
        )
    if response.headers.get("content-type") == "application/json":
        return json.dumps(response.json(), indent=4)
    return response.text


if __name__ == "__main__":
    print(invoke())
