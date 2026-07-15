from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ownyourcode.main import app
from ownyourcode.modules.lessons.evidence import build_evidence_catalog
from ownyourcode.modules.repositories.schemas import (
    DetectedLanguage,
    DetectedTechnology,
    ImportantFile,
    InspectedPaths,
    RepositoryInspectionResponse,
    RepositoryMetadata,
)
from ownyourcode.modules.security_challenges.schemas import (
    ALLOWED_ORIGIN_CHECK_ID,
    CREDENTIALS_SETTING_CHECK_ID,
    FIXTURE_STRUCTURE_CHECK_ID,
    MAX_SECURITY_CHALLENGE_SOURCE_LENGTH,
    MIDDLEWARE_CONFIGURATION_CHECK_ID,
    SYNTAX_VALID_CHECK_ID,
    SecurityChallengeEvaluationRequest,
    SecurityChallengeEvaluationResponse,
    SecurityChallengePrepareRequest,
)
from ownyourcode.modules.security_challenges.service import (
    FastAPICorsSecurityChallengeService,
    SecurityChallengeContextStaleError,
    _challenge_context_fingerprint,
    _relevant_evidence,
)
from ownyourcode.modules.security_challenges.verifier import (
    REQUIRED_ALLOWED_ORIGIN,
    verify_fastapi_cors_fixture,
)
import ownyourcode.modules.security_challenges.verifier as cors_verifier


VALID_SOURCE = f'''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["{REQUIRED_ALLOWED_ORIGIN}"],
    allow_credentials=True,
)
'''

CHECK_IDS = [
    SYNTAX_VALID_CHECK_ID,
    FIXTURE_STRUCTURE_CHECK_ID,
    MIDDLEWARE_CONFIGURATION_CHECK_ID,
    ALLOWED_ORIGIN_CHECK_ID,
    CREDENTIALS_SETTING_CHECK_ID,
]


def inspection_response(
    *,
    languages: list[DetectedLanguage] | None = None,
    technologies: list[DetectedTechnology] | None = None,
    html_url: str = "https://github.com/acme/learning-api",
    fastapi_evidence: str = "pyproject.toml: dependency fastapi",
) -> RepositoryInspectionResponse:
    return RepositoryInspectionResponse(
        repository=RepositoryMetadata(
            name="learning-api",
            full_name="acme/learning-api",
            description="A public learning API.",
            default_branch="main",
            primary_language="Python",
            html_url=html_url,
        ),
        languages=languages
        if languages is not None
        else [DetectedLanguage(name="Python", bytes=1200)],
        technologies=technologies
        if technologies is not None
        else [
            DetectedTechnology(
                key="fastapi",
                label="FastAPI",
                evidence=[fastapi_evidence],
            )
        ],
        paths=InspectedPaths(inspected_count=3, returned=["pyproject.toml"], truncated=False),
        important_files=[ImportantFile(path="pyproject.toml", kind="manifest")],
        limitations=["Inspection uses a bounded deterministic catalog."],
    )


class FakeInspectionService:
    def __init__(self, responses: list[RepositoryInspectionResponse]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    def inspect_url(self, repository_url: str) -> RepositoryInspectionResponse:
        self.calls.append(repository_url)
        index = min(len(self.calls) - 1, len(self._responses) - 1)
        return self._responses[index]


def prepare_request(
    repository_url: str = "https://github.com/acme/learning-api",
) -> SecurityChallengePrepareRequest:
    return SecurityChallengePrepareRequest(
        repository_url=repository_url,
        learner_level="beginner",
    )


def prepared_challenge(
    service: FastAPICorsSecurityChallengeService,
    repository_url: str = "https://github.com/acme/learning-api",
):
    response = service.prepare(prepare_request(repository_url))
    assert response.available is True
    return response


def evaluation_request(
    context_id: str,
    source_code: str = VALID_SOURCE,
) -> SecurityChallengeEvaluationRequest:
    return SecurityChallengeEvaluationRequest(
        repository_url="https://github.com/acme/learning-api",
        learner_level="beginner",
        security_challenge_context_id=context_id,
        source_code=source_code,
    )


def test_confirmed_python_fastapi_evidence_prepares_the_challenge_with_inspected_url() -> None:
    inspection = inspection_response(html_url="https://github.com/inspected/learning-api")
    service = FastAPICorsSecurityChallengeService(
        FakeInspectionService([inspection])  # type: ignore[arg-type]
    )

    response = prepared_challenge(service)

    relevant_evidence = _relevant_evidence(build_evidence_catalog(inspection))
    assert relevant_evidence is not None
    assert response.security_challenge_context_id == _challenge_context_fingerprint(
        repository_url="https://github.com/inspected/learning-api",
        learner_level="beginner",
        relevant_evidence=relevant_evidence,
    )
    assert response.persisted is False
    assert REQUIRED_ALLOWED_ORIGIN in response.instructions
    assert "not source code from the inspected repository" in response.instructions
    assert "does not scan the repository" in response.instructions


def test_exact_evidence_ids_control_availability_not_misleading_labels() -> None:
    misleading_labels = inspection_response(
        languages=[],
        technologies=[
            DetectedTechnology(key="nodejs", label="Python", evidence=["package.json"]),
            DetectedTechnology(key="flask", label="FastAPI", evidence=["requirements.txt"]),
        ],
    )
    unavailable = FastAPICorsSecurityChallengeService(
        FakeInspectionService([misleading_labels])  # type: ignore[arg-type]
    ).prepare(prepare_request())
    assert unavailable.available is False

    supported_through_technology = inspection_response(
        languages=[],
        technologies=[
            DetectedTechnology(key="python", label="Other runtime", evidence=["requirements.txt"]),
            DetectedTechnology(key="fastapi", label="Other framework", evidence=["pyproject.toml"]),
        ],
    )
    assert prepared_challenge(
        FastAPICorsSecurityChallengeService(
            FakeInspectionService([supported_through_technology])  # type: ignore[arg-type]
        )
    ).available is True


def test_exact_valid_fixture_with_comments_and_trailing_newlines_passes() -> None:
    source = f'''# Server-owned teaching fixture
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()  # fixed application construction

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["{REQUIRED_ALLOWED_ORIGIN}"],
)

# trailing comment

'''

    verification = verify_fastapi_cors_fixture(source)

    assert verification.passed is True
    assert [check.id for check in verification.checks] == CHECK_IDS


def test_valid_fixture_does_not_depend_on_ast_walk_call_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_walk = cors_verifier.ast.walk

    def reverse_walk(node):  # type: ignore[no-untyped-def]
        return iter(reversed(list(original_walk(node))))

    monkeypatch.setattr(cors_verifier.ast, "walk", reverse_walk)

    verification = verify_fastapi_cors_fixture(VALID_SOURCE)

    assert [check.passed for check in verification.checks] == [True] * 5


@pytest.mark.parametrize(
    "source_code",
    [
        VALID_SOURCE.replace(
            f'["{REQUIRED_ALLOWED_ORIGIN}"]',
            "[FastAPI()]",
        ),
        VALID_SOURCE + "FastAPI()\n",
    ],
)
def test_only_the_two_validated_fixture_calls_are_accepted(source_code: str) -> None:
    verification = verify_fastapi_cors_fixture(source_code)

    assert verification.passed is False
    assert verification.checks[1].id == FIXTURE_STRUCTURE_CHECK_ID
    assert verification.checks[1].passed is False


def test_expected_challenge_results_remain_unchanged_for_valid_and_wrong_origin() -> None:
    valid = verify_fastapi_cors_fixture(VALID_SOURCE)
    wrong_origin = verify_fastapi_cors_fixture(
        VALID_SOURCE.replace(REQUIRED_ALLOWED_ORIGIN, "*")
    )

    assert [check.passed for check in valid.checks] == [True] * 5
    assert [check.passed for check in wrong_origin.checks] == [
        True,
        True,
        True,
        False,
        True,
    ]


@pytest.mark.parametrize(
    "source_code",
    [
        VALID_SOURCE.replace(
            "from fastapi import FastAPI\nfrom fastapi.middleware.cors import CORSMiddleware",
            "from fastapi.middleware.cors import CORSMiddleware\nfrom fastapi import FastAPI",
        ),
        VALID_SOURCE.replace("from fastapi import FastAPI", "from fastapi import FastAPI as Framework"),
        VALID_SOURCE.replace(
            "from fastapi.middleware.cors import CORSMiddleware",
            "from fastapi.middleware.cors import CORSMiddleware as Middleware",
        ),
        VALID_SOURCE + "FastAPI()\n",
        VALID_SOURCE.replace("app = FastAPI()", "app = FastAPI()\nextra = 1"),
    ],
)
def test_reordered_or_aliased_imports_extra_calls_and_statements_are_rejected(
    source_code: str,
) -> None:
    verification = verify_fastapi_cors_fixture(source_code)

    assert verification.passed is False
    assert verification.checks[1].id == FIXTURE_STRUCTURE_CHECK_ID
    assert verification.checks[1].passed is False


@pytest.mark.parametrize(
    "source_code",
    [
        VALID_SOURCE.replace(
            'allow_origins=["http://localhost:5173"],\n    allow_credentials=True,',
            'allow_origins=["http://localhost:5173"],\n    **{"allow_credentials": True},',
        ),
        VALID_SOURCE.replace(
            'allow_origins=["http://localhost:5173"],\n    allow_credentials=True,',
            'allow_origins=["http://localhost:5173"],\n    allow_origins=["http://localhost:5173"],',
        ),
        VALID_SOURCE.replace("allow_credentials=True,", "allow_methods=[\"GET\"],"),
        VALID_SOURCE.replace("allow_credentials=True,", "allow_credentials=1,"),
        VALID_SOURCE.replace(
            '["http://localhost:5173"]',
            '("http://localhost:5173",)',
        ),
        VALID_SOURCE.replace(
            '["http://localhost:5173"]',
            '["http://localhost:" + "5173"]',
        ),
    ],
)
def test_keyword_unpacking_invalid_keywords_and_nonliteral_values_are_rejected(
    source_code: str,
) -> None:
    verification = verify_fastapi_cors_fixture(source_code)

    assert verification.passed is False


def test_wrong_origin_is_reported_without_claiming_the_origin_check_passed() -> None:
    verification = verify_fastapi_cors_fixture(
        VALID_SOURCE.replace(REQUIRED_ALLOWED_ORIGIN, "*")
    )

    assert verification.checks[2].passed is True
    assert verification.checks[3].id == ALLOWED_ORIGIN_CHECK_ID
    assert verification.checks[3].passed is False
    assert verification.checks[4].passed is True


def test_integer_one_is_not_accepted_as_literal_boolean_true() -> None:
    verification = verify_fastapi_cors_fixture(
        VALID_SOURCE.replace("allow_credentials=True", "allow_credentials=1")
    )

    assert verification.checks[2].passed is True
    assert verification.checks[3].passed is True
    assert verification.checks[4].id == CREDENTIALS_SETTING_CHECK_ID
    assert verification.checks[4].passed is False


def test_malformed_syntax_preserves_all_check_ids_with_safe_dependent_wording() -> None:
    verification = verify_fastapi_cors_fixture("from fastapi import FastAPI\napp = FastAPI(\n")

    assert [check.id for check in verification.checks] == CHECK_IDS
    assert verification.checks[0].passed is False
    assert all(
        check.message == "Not evaluated because the submitted Python syntax is invalid."
        for check in verification.checks[1:]
    )


def test_source_validation_and_direct_verifier_handle_surrogates_without_execution(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        SecurityChallengeEvaluationRequest(
            repository_url="https://github.com/acme/learning-api",
            learner_level="beginner",
            security_challenge_context_id="a" * 64,
            source_code=VALID_SOURCE + "\ud800",
        )
    with pytest.raises(ValidationError):
        SecurityChallengeEvaluationRequest(
            repository_url="https://github.com/acme/learning-api",
            learner_level="beginner",
            security_challenge_context_id="a" * 64,
            source_code="x" * (MAX_SECURITY_CHALLENGE_SOURCE_LENGTH + 1),
        )

    marker = tmp_path / "must-not-exist-after-surrogate.txt"
    malicious_source = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "from fastapi import FastAPI\n"
        "from fastapi.middleware.cors import CORSMiddleware\n"
        "app = FastAPI()\n"
        "app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True)\n"
        "\ud800"
    )
    verification = verify_fastapi_cors_fixture(malicious_source)

    assert [check.id for check in verification.checks] == CHECK_IDS
    assert verification.passed is False
    assert marker.exists() is False


def test_malicious_looking_valid_python_is_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist.txt"
    source_code = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        + VALID_SOURCE
    )

    verification = verify_fastapi_cors_fixture(source_code)

    assert verification.passed is False
    assert verification.checks[1].passed is False
    assert marker.exists() is False


def test_response_requires_passed_to_match_every_check() -> None:
    valid_checks = verify_fastapi_cors_fixture(VALID_SOURCE).checks
    failed_checks = verify_fastapi_cors_fixture(
        VALID_SOURCE.replace(REQUIRED_ALLOWED_ORIGIN, "*")
    ).checks

    assert SecurityChallengeEvaluationResponse(
        passed=True,
        checks=valid_checks,
        feedback=["Passed."],
        inspection_limitations=["Inspection is bounded."],
    ).passed is True
    assert SecurityChallengeEvaluationResponse(
        passed=False,
        checks=failed_checks,
        feedback=["Try again."],
        inspection_limitations=["Inspection is bounded."],
    ).passed is False

    with pytest.raises(ValidationError):
        SecurityChallengeEvaluationResponse(
            passed=False,
            checks=valid_checks,
            feedback=["Inconsistent."],
            inspection_limitations=["Inspection is bounded."],
        )
    with pytest.raises(ValidationError):
        SecurityChallengeEvaluationResponse(
            passed=True,
            checks=failed_checks,
            feedback=["Inconsistent."],
            inspection_limitations=["Inspection is bounded."],
        )


def test_stale_context_is_rejected_after_reinspection() -> None:
    first_inspection = inspection_response()
    changed_inspection = inspection_response(
        fastapi_evidence="requirements.txt: dependency fastapi"
    )
    service = FastAPICorsSecurityChallengeService(
        FakeInspectionService([first_inspection, changed_inspection])  # type: ignore[arg-type]
    )
    challenge = prepared_challenge(service)

    with pytest.raises(SecurityChallengeContextStaleError):
        service.evaluate(evaluation_request(challenge.security_challenge_context_id))


def test_routes_use_mocked_inspection_without_github_or_openai_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FastAPICorsSecurityChallengeService(
        FakeInspectionService([inspection_response()])  # type: ignore[arg-type]
    )
    monkeypatch.setattr(
        "ownyourcode.modules.security_challenges.router.create_fastapi_cors_security_challenge_service",
        lambda: service,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/security-challenges/fastapi-cors/prepare",
        json={
            "repository_url": "https://github.com/acme/learning-api",
            "learner_level": "beginner",
        },
    )

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["persisted"] is False
