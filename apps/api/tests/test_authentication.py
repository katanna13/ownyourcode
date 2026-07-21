from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from ownyourcode.db.session import get_db_session
from ownyourcode.main import app
from ownyourcode.modules.authentication.dependencies import get_auth_token_verifier
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.authentication.service import resolve_internal_user
from ownyourcode.modules.authentication.verifier import (
    AuthenticatedSubject,
    ClerkAuthTokenVerifier,
    InvalidAuthenticationError,
    TestAuthTokenVerifier,
)
from ownyourcode.core.config import ClerkAuthConfiguration, Settings


def test_missing_invalid_and_expired_tokens_are_rejected(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    verifier = TestAuthTokenVerifier({"valid": AuthenticatedSubject("user_valid")})

    def override_session():  # type: ignore[no-untyped-def]
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_auth_token_verifier] = lambda: verifier
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/me").status_code == 401
            assert (
                client.get(
                    "/api/v1/me", headers={"Authorization": "Bearer invalid"}
                ).status_code
                == 401
            )
            assert (
                client.get(
                    "/api/v1/me", headers={"Authorization": "Bearer expired"}
                ).status_code
                == 401
            )
    finally:
        app.dependency_overrides.clear()


def test_first_authenticated_request_creates_and_later_request_reuses_user(
    test_session_factory,
) -> None:  # type: ignore[no-untyped-def]
    verifier = TestAuthTokenVerifier({"valid": AuthenticatedSubject("user_one")})

    def override_session():  # type: ignore[no-untyped-def]
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_auth_token_verifier] = lambda: verifier
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/me", headers={"Authorization": "Bearer valid"})
            second = client.get("/api/v1/me", headers={"Authorization": "Bearer valid"})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()
        with test_session_factory() as session:
            assert session.scalar(select(func.count()).select_from(User)) == 1
    finally:
        app.dependency_overrides.clear()


def test_concurrent_first_user_upserts_create_one_user(test_session_factory) -> None:  # type: ignore[no-untyped-def]
    def resolve_once() -> str:
        with test_session_factory() as session:
            return str(resolve_internal_user(session, "concurrent_subject").id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        ids = list(executor.map(lambda _: resolve_once(), range(2)))

    assert ids[0] == ids[1]
    with test_session_factory() as session:
        assert session.scalar(select(func.count()).select_from(User)) == 1


def test_clerk_adapter_uses_networkless_session_verification_and_checks_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def signed_in_request(request, options):  # type: ignore[no-untyped-def]
        captured["authorization"] = request.headers["Authorization"]
        captured["options"] = options
        from clerk_backend_api.security.types import AuthStatus

        return SimpleNamespace(
            status=AuthStatus.SIGNED_IN,
            payload={"iss": "https://issuer.example", "sub": "user_clerk"},
        )

    monkeypatch.setattr(
        "ownyourcode.modules.authentication.verifier.authenticate_request",
        signed_in_request,
    )
    verifier = ClerkAuthTokenVerifier(
        ClerkAuthConfiguration(
            jwt_key="public verification key",
            issuer="https://issuer.example",
            audience=("ownyourcode-api",),
            authorized_parties=("http://localhost:5173",),
        )
    )

    assert verifier.verify_session_token("short-lived-token") == AuthenticatedSubject(
        "user_clerk"
    )
    options = captured["options"]
    assert captured["authorization"] == "Bearer short-lived-token"
    assert options.jwt_key == "public verification key"
    assert options.secret_key is None
    assert options.audience == ["ownyourcode-api"]
    assert options.authorized_parties == ["http://localhost:5173"]
    assert options.accepts_token == ["session_token"]


@pytest.mark.parametrize(
    "payload",
    [
        {"iss": "https://other.example", "sub": "user_clerk"},
        {"iss": "https://issuer.example", "sub": ""},
        {
            "iss": "https://issuer.example",
            "sub": "user_clerk",
            "session_status": "revoked",
        },
    ],
)
def test_clerk_adapter_rejects_invalid_issuer_subject_or_active_status(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, str]
) -> None:
    def signed_in_request(request, options):  # type: ignore[no-untyped-def]
        from clerk_backend_api.security.types import AuthStatus

        return SimpleNamespace(status=AuthStatus.SIGNED_IN, payload=payload)

    monkeypatch.setattr(
        "ownyourcode.modules.authentication.verifier.authenticate_request",
        signed_in_request,
    )
    verifier = ClerkAuthTokenVerifier(
        ClerkAuthConfiguration(
            jwt_key="public verification key",
            issuer="https://issuer.example",
            audience=(),
            authorized_parties=("http://localhost:5173",),
        )
    )
    with pytest.raises(InvalidAuthenticationError):
        verifier.verify_session_token("invalid-token")


def test_clerk_configuration_parses_comma_separated_origins_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLERK_JWT_KEY", "public verification key")
    monkeypatch.setenv("CLERK_ISSUER", "https://issuer.example/")
    monkeypatch.setenv("CLERK_AUDIENCE", "ownyourcode-api, mobile-client")
    monkeypatch.setenv(
        "CLERK_AUTHORIZED_PARTIES", "http://localhost:5173/,https://app.example"
    )
    configuration = Settings(_env_file=None).clerk_auth_configuration()
    assert configuration.issuer == "https://issuer.example"
    assert configuration.audience == ("ownyourcode-api", "mobile-client")
    assert configuration.authorized_parties == (
        "http://localhost:5173",
        "https://app.example",
    )

    monkeypatch.setenv("CLERK_AUTHORIZED_PARTIES", "*")
    with pytest.raises(ValueError, match="wildcard"):
        Settings(_env_file=None).clerk_auth_configuration()


def test_unconfigured_authentication_fails_closed_only_for_protected_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ownyourcode.modules.authentication.dependencies as dependencies

    class MissingConfiguration:
        def clerk_auth_configuration(self):  # type: ignore[no-untyped-def]
            raise ValueError("missing configuration")

    monkeypatch.setattr(dependencies, "get_settings", lambda: MissingConfiguration())
    with TestClient(app) as client:
        protected = client.get("/api/v1/me")
        public = client.post(
            "/api/v1/projects/preview",
            json={
                "name": "Public Demo",
                "description": "This public demo remains available without sign-in.",
                "mode": "new_idea",
            },
        )

    assert protected.status_code == 503
    assert protected.json() == {"detail": "Authentication is not configured."}
    assert public.status_code == 200
