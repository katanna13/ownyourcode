from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Return API process liveness without contacting external services."""
    return {"status": "ok",
                "service": "ownyourcode-api",
   }

