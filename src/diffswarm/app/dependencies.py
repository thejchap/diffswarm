from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_session
from .settings import Settings, get_settings

SessionDependency = Annotated[Session, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
