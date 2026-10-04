from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.app.core.config import Settings
from backend.app.db.session import create_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = None
    app.state.session_factory = None
    try:
        settings = Settings()
    except ValidationError:
        pass
    else:
        app.state.db_engine = create_engine(settings)
        app.state.session_factory = async_sessionmaker(
            app.state.db_engine, expire_on_commit=False
        )
    try:
        yield
    finally:
        if app.state.db_engine is not None:
            await app.state.db_engine.dispose()
1