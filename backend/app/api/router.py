from fastapi import APIRouter

from backend.app.api.routes.health import router as health_router
from backend.app.api.v1.routes.auth import router as auth_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
