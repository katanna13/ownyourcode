from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from ownyourcode.main import app
from ownyourcode.modules.labs.schemas import (
    HEALTH_CHECK_CONTRACT_CHECK_ID,
    LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
    MAX_LAB_SOURCE_LENGTH,
    RESTRICTED_STRUCTURE_CHECK_ID,
    SYNTAX_VALID_CHECK_ID,
    LabEvaluationRequest,
    LabEvaluationResponse,
    LabPrepareRequest,
)
from ownyourcode.modules.labs.service import (
    FastAPIHealthCheckLabService,
    LabContextStaleError,
    _lab_context_fingerprint,
    _relevant_evidence,
)
from ownyourcode.modules.labs.verifier import verify_fastapi_health_check
from ownyourcode.modules.lessons.evidence import build_evidence_catalog
from ownyourcode.modules.repositories.schemas import (
    DetectedLanguage,
    DetectedTechnology,
    ImportantFile,
    InspectedPaths,
    RepositoryInspectionResponse,
    RepositoryMetadata,
)


VALID_SOURCE = '''def healthz():
    return {"status": "ok", "service": "ownyourcode-api"}
'''


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
        languages=languages if languages is not None else [DetectedLanguage(name="Python", bytes=1200)],
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


def prepare_request(repository_url: str = "https://github.com/acme/learning-api") -> LabPrepareRequest:
    return LabPrepareRequest(repository_url=repository_url, learner_level="beginner")


def prepared_lab(
    service: FastAPIHealthCheckLabService,
    repository_url: str = "https://github.com/acme/learning-api",
):
    response = service.prepare(prepare_request(repository_url))
    assert response.available is True
    return response


def evaluation_request(lab_context_id: str, source_code: str = VALID_SOURCE) -> LabEvaluationRequest:
    return LabEvaluationRequest(
        repository_url="https://github.com/acme/learning-api",
        learner_level="beginner",
        lab_context_id=lab_context_id,
        source_code=source_code,
    )


def test_supported_python_fastapi_repository_receives_lab_and_uses_inspected_url() -> None:
    inspection = inspection_response(html_url="https://github.com/inspected/learning-api")
    service = FastAPIHealthCheckLabService(FakeInspectionService([inspection]))  # type: ignore[arg-type]

    response = prepared_lab(service)

    relevant_evidence = _relevant_evidence(build_evidence_catalog(inspection))
    assert relevant_evidence is not None
    assert response.lab_context_id == _lab_context_fingerprint(
        repository_url="https://github.com/inspected/learning-api",
        learner_level="beginner",
        relevant_evidence=relevant_evidence,
    )
    assert response.persisted is False
    assert response.starter_code == 'def healthz():\n    return {"status": "ok"}\n'


def test_equivalent_accepted_urls_have_the_same_inspected_context() -> None:
    inspection = inspection_response()
    first = prepared_lab(
        FastAPIHealthCheckLabService(FakeInspectionService([inspection])),  # type: ignore[arg-type]
        "https://github.com/acme/learning-api",
    )
    second = prepared_lab(
        FastAPIHealthCheckLabService(FakeInspectionService([inspection])),  # type: ignore[arg-type]
        "https://github.com/acme/learning-api/",
    )

    assert first.lab_context_id == second.lab_context_id


def test_exact_evidence_ids_control_lab_availability_not_misleading_labels() -> None:
    supported_with_technology_python = inspection_response(
        languages=[],
        technologies=[
            DetectedTechnology(key="python", label="Other runtime", evidence=["requirements.txt"]),
            DetectedTechnology(key="fastapi", label="Other framework", evidence=["pyproject.toml"]),
        ],
    )
    supported_service = FastAPIHealthCheckLabService(
        FakeInspectionService([supported_with_technology_python])  # type: ignore[arg-type]
    )
    assert prepared_lab(supported_service).available is True

    misleading_labels = inspection_response(
        languages=[],
        technologies=[
            DetectedTechnology(key="nodejs", label="Python", evidence=["package.json"]),
            DetectedTechnology(key="flask", label="FastAPI", evidence=["requirements.txt"]),
        ],
    )
    response = FastAPIHealthCheckLabService(
        FakeInspectionService([misleading_labels])  # type: ignore[arg-type]
    ).prepare(prepare_request())
    assert response.available is False


def test_valid_solution_passes_with_dictionary_key_order_independent() -> None:
    service = FastAPIHealthCheckLabService(FakeInspectionService([inspection_response()]))  # type: ignore[arg-type]
    lab = prepared_lab(service)
    source = '''# ordinary comment
def healthz():
    return {"service": "ownyourcode-api", "status": "ok"}  # still data only

# trailing comment
'''

    response = service.evaluate(evaluation_request(lab.lab_context_id, source))

    assert response.passed is True
    assert [check.id for check in response.checks] == [
        SYNTAX_VALID_CHECK_ID,
        RESTRICTED_STRUCTURE_CHECK_ID,
        LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
        HEALTH_CHECK_CONTRACT_CHECK_ID,
    ]


@pytest.mark.parametrize(
    "source_code",
    [
        'def healthz():\n    return {"status": "ok"}\n',
        'def healthz():\n    return {"status": "ok", "service": "wrong"}\n',
        'def healthz():\n    return {"status": "ok", "status": "ok"}\n',
        'def healthz():\n    return {"status": "ok", "service": "ownyourcode-api", "extra": "no"}\n',
    ],
)
def test_missing_wrong_duplicate_or_extra_response_fields_fail(source_code: str) -> None:
    verification = verify_fastapi_health_check(source_code)
    assert verification.passed is False
    assert verification.checks[-1].passed is False


@pytest.mark.parametrize(
    "source_code",
    [
        'import os\ndef healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n',
        'def healthz():\n    return {"status": str("ok"), "service": "ownyourcode-api"}\n',
        'def healthz():\n    return {"status": "ok", "service": "ownyourcode-api"}\n\ndef extra():\n    return {}\n',
    ],
)
def test_imports_calls_and_extra_functions_are_rejected(source_code: str) -> None:
    verification = verify_fastapi_health_check(source_code)
    assert verification.passed is False
    assert verification.checks[1].id == RESTRICTED_STRUCTURE_CHECK_ID
    assert verification.checks[1].passed is False


def test_malformed_python_preserves_all_check_ids_with_safe_dependent_wording() -> None:
    verification = verify_fastapi_health_check("def healthz(:\n    return {}\n")

    assert [check.id for check in verification.checks] == [
        SYNTAX_VALID_CHECK_ID,
        RESTRICTED_STRUCTURE_CHECK_ID,
        LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
        HEALTH_CHECK_CONTRACT_CHECK_ID,
    ]
    assert verification.checks[0].passed is False
    assert all(
        check.message == "Not evaluated because the submitted Python syntax is invalid."
        for check in verification.checks[1:]
    )


def test_source_length_and_control_characters_are_rejected_without_altering_code() -> None:
    with pytest.raises(ValidationError):
        LabEvaluationRequest(
            repository_url="https://github.com/acme/learning-api",
            learner_level="beginner",
            lab_context_id="a" * 64,
            source_code="x" * (MAX_LAB_SOURCE_LENGTH + 1),
        )
    with pytest.raises(ValidationError):
        LabEvaluationRequest(
            repository_url="https://github.com/acme/learning-api",
            learner_level="beginner",
            lab_context_id="a" * 64,
            source_code="def healthz():\n\treturn {}\x00\n",
        )
    normalized = LabEvaluationRequest(
        repository_url="https://github.com/acme/learning-api",
        learner_level="beginner",
        lab_context_id="a" * 64,
        source_code="def healthz():\r\n    return {}\r",
    )
    assert normalized.source_code == "def healthz():\n    return {}\n"


def test_lone_surrogate_is_rejected_by_request_validation_and_safe_direct_parsing(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError):
        LabEvaluationRequest(
            repository_url="https://github.com/acme/learning-api",
            learner_level="beginner",
            lab_context_id="a" * 64,
            source_code="def healthz():\n    return {}\n\ud800",
        )

    marker = tmp_path / "must-not-exist-after-surrogate.txt"
    malicious_source = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def healthz():\n"
        '    return {"status": "ok", "service": "ownyourcode-api"}\n'
        "\ud800"
    )
    verification = verify_fastapi_health_check(malicious_source)

    assert [check.id for check in verification.checks] == [
        SYNTAX_VALID_CHECK_ID,
        RESTRICTED_STRUCTURE_CHECK_ID,
        LITERAL_RESPONSE_DICTIONARY_CHECK_ID,
        HEALTH_CHECK_CONTRACT_CHECK_ID,
    ]
    assert verification.passed is False
    assert marker.exists() is False


def test_malicious_code_is_parsed_but_never_executed(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist.txt"
    source_code = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "def healthz():\n"
        '    return {"status": "ok", "service": "ownyourcode-api"}\n'
    )

    verification = verify_fastapi_health_check(source_code)

    assert verification.passed is False
    assert verification.checks[1].passed is False
    assert marker.exists() is False


def test_evaluation_response_requires_passed_to_match_every_check() -> None:
    valid_checks = verify_fastapi_health_check(VALID_SOURCE).checks
    failed_checks = verify_fastapi_health_check(
        'def healthz():\n    return {"status": "ok"}\n'
    ).checks

    valid_response = LabEvaluationResponse(
        passed=True,
        checks=valid_checks,
        feedback=["Passed."],
        inspection_limitations=["Inspection is bounded."],
    )
    failed_response = LabEvaluationResponse(
        passed=False,
        checks=failed_checks,
        feedback=["Try again."],
        inspection_limitations=["Inspection is bounded."],
    )
    assert valid_response.passed is True
    assert failed_response.passed is False

    with pytest.raises(ValidationError):
        LabEvaluationResponse(
            passed=False,
            checks=valid_checks,
            feedback=["Inconsistent."],
            inspection_limitations=["Inspection is bounded."],
        )
    with pytest.raises(ValidationError):
        LabEvaluationResponse(
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
    service = FastAPIHealthCheckLabService(
        FakeInspectionService([first_inspection, changed_inspection])  # type: ignore[arg-type]
    )
    lab = prepared_lab(service)

    with pytest.raises(LabContextStaleError):
        service.evaluate(evaluation_request(lab.lab_context_id))


def test_routes_use_mocked_inspection_without_github_or_openai_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = FastAPIHealthCheckLabService(FakeInspectionService([inspection_response()]))  # type: ignore[arg-type]
    monkeypatch.setattr(
        "ownyourcode.modules.labs.router.create_fastapi_health_check_lab_service",
        lambda: service,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/labs/fastapi-health-check/prepare",
        json={
            "repository_url": "https://github.com/acme/learning-api",
            "learner_level": "beginner",
        },
    )

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["persisted"] is False
