from typing import Annotated

from fastapi import APIRouter, Depends

from ownyourcode.modules.authentication.dependencies import get_current_user
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.authentication.schemas import CurrentUserResponse


router = APIRouter(tags=["authentication"])


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse(id=current_user.id)
