from fastapi import APIRouter

from ownyourcode.api.routes.health import router as health_router
from ownyourcode.modules.projects.router import router as projects_router

router = APIRouter()
router.include_router(health_router)
router.include_router(projects_router, prefix="/api/v1/projects")
