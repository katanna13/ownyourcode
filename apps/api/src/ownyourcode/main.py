from fastapi import FastAPI

from ownyourcode.api.router import router
from ownyourcode.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="OwnYourCode API",
    version="0.1.0",
    debug=settings.app_env == "development",
)
app.include_router(router)
