from fastapi import APIRouter
from ulid import ULID

from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import DiffBase, DiffSwarmBaseModel

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: DiffBase


@ROUTER.get("/diffs/{_diff_id}")
def get_diff(_diff_id: ULID, _session: SessionDependency) -> GetDiffResponse:
    return GetDiffResponse(diff=DiffBase.parse_str(DiffBase.HELLO_WORLD))
