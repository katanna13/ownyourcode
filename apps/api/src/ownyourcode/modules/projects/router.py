from fastapi import APIRouter

from ownyourcode.modules.projects.schemas import (
    ProjectPreviewRequest,
    ProjectPreviewResponse,
)

router = APIRouter(tags=["projects"])


@router.post("/preview", response_model=ProjectPreviewResponse)
def preview_project(project: ProjectPreviewRequest) -> ProjectPreviewResponse:
    """Validate project details and return them without saving anything."""
    return ProjectPreviewResponse(project=project)
