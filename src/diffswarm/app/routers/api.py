from fastapi import APIRouter
from ulid import ULID

from diffswarm.app.database import DBDiff
from diffswarm.app.dependencies import SessionDependency
from diffswarm.app.models import Diff, DiffSwarmBaseModel

ROUTER = APIRouter()


class GetDiffResponse(DiffSwarmBaseModel):
    diff: Diff


@ROUTER.get("/diffs/{diff_id}")
def get_diff(diff_id: ULID, session: SessionDependency) -> GetDiffResponse:
    diff = Diff.model_validate(
        session.query(DBDiff.id, DBDiff.raw).filter(DBDiff.id == str(diff_id)).one()
    )
    return GetDiffResponse(diff=diff)
