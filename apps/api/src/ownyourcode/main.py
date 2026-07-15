from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ownyourcode.api.router import router
from ownyourcode.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="OwnYourCode API",
    version="0.1.0",
    debug=settings.app_env == "development",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
