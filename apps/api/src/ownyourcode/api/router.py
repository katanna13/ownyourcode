from fastapi import APIRouter

from ownyourcode.api.routes.health import router as health_router
from ownyourcode.modules.assessments.router import router as assessments_router
from ownyourcode.modules.labs.router import router as labs_router
from ownyourcode.modules.lessons.router import router as lessons_router
from ownyourcode.modules.projects.router import router as projects_router
from ownyourcode.modules.repositories.router import router as repositories_router
from ownyourcode.modules.security_challenges.router import (
    router as security_challenges_router,
)

router = APIRouter()
router.include_router(health_router)
router.include_router(projects_router, prefix="/api/v1/projects")
router.include_router(repositories_router, prefix="/api/v1/repositories")
router.include_router(lessons_router, prefix="/api/v1/lessons")
router.include_router(assessments_router, prefix="/api/v1/assessments")
router.include_router(labs_router, prefix="/api/v1/labs")
router.include_router(security_challenges_router, prefix="/api/v1/security-challenges")
