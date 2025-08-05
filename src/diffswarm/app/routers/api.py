from fastapi import APIRouter

from diffswarm.app.models import DiffSwarmBaseModel

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: None = None


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: str) -> GetDiffResponse:
    _ = diff_id
    return GetDiffResponse(diff=None)
