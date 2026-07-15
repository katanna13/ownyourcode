"""HTTP boundary for the AST-only FastAPI CORS teaching challenge."""

from fastapi import APIRouter, HTTPException

from ownyourcode.core.config import get_settings
from ownyourcode.modules.lessons.evidence import EvidenceCatalogError
from ownyourcode.modules.repositories.github_client import GitHubClientError
from ownyourcode.modules.repositories.service import PublicRepositoryInspectionService
from ownyourcode.modules.security_challenges.schemas import (
    FastAPICorsSecurityChallengePrepareResponse,
    SecurityChallengeEvaluationRequest,
    SecurityChallengeEvaluationResponse,
    SecurityChallengePrepareRequest,
)
from ownyourcode.modules.security_challenges.service import (
    FastAPICorsSecurityChallengeService,
    SecurityChallengeContextStaleError,
    SecurityChallengeEvidenceError,
    SecurityChallengeUnavailableError,
)


router = APIRouter(tags=["security challenges"])


def create_fastapi_cors_security_challenge_service() -> FastAPICorsSecurityChallengeService:
    """Small construction seam for tests; no execution worker is involved."""

    return FastAPICorsSecurityChallengeService(
        PublicRepositoryInspectionService(github_token=get_settings().github_token)
    )


@router.post(
    "/fastapi-cors/prepare",
    response_model=FastAPICorsSecurityChallengePrepareResponse,
)
def prepare_fastapi_cors_security_challenge(
    request: SecurityChallengePrepareRequest,
) -> FastAPICorsSecurityChallengePrepareResponse:
    try:
        return create_fastapi_cors_security_challenge_service().prepare(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except (EvidenceCatalogError, SecurityChallengeEvidenceError) as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely for this security challenge.",
        ) from error


@router.post(
    "/fastapi-cors/evaluate",
    response_model=SecurityChallengeEvaluationResponse,
)
def evaluate_fastapi_cors_security_challenge(
    request: SecurityChallengeEvaluationRequest,
) -> SecurityChallengeEvaluationResponse:
    try:
        return create_fastapi_cors_security_challenge_service().evaluate(request)
    except GitHubClientError as error:
        raise HTTPException(status_code=error.status_code, detail=error.public_message) from error
    except SecurityChallengeUnavailableError as error:
        raise HTTPException(
            status_code=422,
            detail="This security challenge requires deterministic Python and FastAPI evidence.",
        ) from error
    except SecurityChallengeContextStaleError as error:
        raise HTTPException(
            status_code=409,
            detail="Repository evidence changed. Prepare the security challenge again before submitting.",
        ) from error
    except (EvidenceCatalogError, SecurityChallengeEvidenceError) as error:
        raise HTTPException(
            status_code=502,
            detail="Repository evidence could not be prepared safely for this security challenge.",
        ) from error
