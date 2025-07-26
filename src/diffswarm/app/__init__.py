import uvicorn

from .app import APP


def run():
    uvicorn.run(APP)
