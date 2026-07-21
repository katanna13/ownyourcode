from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from clerk_backend_api.security.types import AuthStatus

from ownyourcode.core.config import ClerkAuthConfiguration


class AuthenticationError(Exception):
    """Safe authentication failure with no provider detail exposed."""


class MissingAuthenticationError(AuthenticationError):
    pass


class InvalidAuthenticationError(AuthenticationError):
    pass


class AuthenticationConfigurationError(AuthenticationError):
    pass


@dataclass(frozen=True)
class AuthenticatedSubject:
    subject: str


class AuthTokenVerifier(Protocol):
    def verify_session_token(self, raw_token: str) -> AuthenticatedSubject:
        """Verify an untrusted token and return only an application-owned subject."""


@dataclass(frozen=True)
class _AuthorizationRequest:
    raw_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.raw_token}"}


class ClerkAuthTokenVerifier:
    """Networkless Clerk adapter. No Clerk types escape this module."""

    def __init__(self, configuration: ClerkAuthConfiguration) -> None:
        self._configuration = configuration

    def verify_session_token(self, raw_token: str) -> AuthenticatedSubject:
        if not raw_token:
            raise MissingAuthenticationError

        try:
            request_state = authenticate_request(
                _AuthorizationRequest(raw_token),
                AuthenticateRequestOptions(
                    jwt_key=self._configuration.jwt_key,
                    audience=list(self._configuration.audience) or None,
                    authorized_parties=list(self._configuration.authorized_parties),
                    accepts_token=["session_token"],
                ),
            )
        except Exception as error:
            raise InvalidAuthenticationError from error

        if request_state.status != AuthStatus.SIGNED_IN or not request_state.payload:
            raise InvalidAuthenticationError

        payload = request_state.payload
        if payload.get("iss") != self._configuration.issuer:
            raise InvalidAuthenticationError

        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise InvalidAuthenticationError

        # Clerk's default session token has no active-status claim. If a configured
        # token template adds one, never accept an explicitly inactive session.
        session_status = payload.get("session_status")
        if session_status is not None and session_status != "active":
            raise InvalidAuthenticationError

        return AuthenticatedSubject(subject=subject)


class TestAuthTokenVerifier:
    """Deterministic test verifier; it never contacts Clerk."""

    __test__ = False

    def __init__(self, tokens: dict[str, AuthenticatedSubject] | None = None) -> None:
        self._tokens = tokens or {}

    def verify_session_token(self, raw_token: str) -> AuthenticatedSubject:
        if not raw_token:
            raise MissingAuthenticationError
        subject = self._tokens.get(raw_token)
        if subject is None:
            raise InvalidAuthenticationError
        return subject
