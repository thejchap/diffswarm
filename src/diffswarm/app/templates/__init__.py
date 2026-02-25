from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

from diffswarm.app.settings import get_settings

ENVIRONMENT = jinja2.Environment(
    undefined=jinja2.StrictUndefined,
    autoescape=True,
    loader=jinja2.FileSystemLoader(Path(__file__).parent),
)
ENVIRONMENT.globals["git_hash"] = get_settings().git_hash  # pyright: ignore[reportArgumentType]
TEMPLATES = Jinja2Templates(env=ENVIRONMENT)
