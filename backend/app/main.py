from fastapi import FastAPI

from backend.app.api.router import router
from backend.app.lifespan import lifespan


def create_app() -> FastAPI:
    app = FastAPI(title="TravelBuddy", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
