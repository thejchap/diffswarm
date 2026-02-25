from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

ENVIRONMENT = jinja2.Environment(
    undefined=jinja2.StrictUndefined,
    autoescape=True,
    loader=jinja2.FileSystemLoader(Path(__file__).parent),
)
TEMPLATES = Jinja2Templates(env=ENVIRONMENT)
