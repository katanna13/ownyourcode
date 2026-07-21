from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ownyourcode.core.config import get_settings
from ownyourcode.db.session import get_db_session
from ownyourcode.modules.authentication.models import User
from ownyourcode.modules.authentication.service import resolve_internal_user
from ownyourcode.modules.authentication.verifier import (
    AuthTokenVerifier,
    AuthenticationError,
    ClerkAuthTokenVerifier,
    InvalidAuthenticationError,
    MissingAuthenticationError,
)


def get_auth_token_verifier() -> AuthTokenVerifier:
    try:
        return ClerkAuthTokenVerifier(get_settings().clerk_auth_configuration())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        ) from None


def raw_bearer_token(authorization: str | None) -> str:
    if authorization is None:
        raise MissingAuthenticationError
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or " " in token:
        raise InvalidAuthenticationError
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    verifier: Annotated[AuthTokenVerifier, Depends(get_auth_token_verifier)] = None,
    session: Annotated[Session, Depends(get_db_session)] = None,
) -> User:
    try:
        subject = verifier.verify_session_token(raw_bearer_token(authorization))
        return resolve_internal_user(session, subject.subject)
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        ) from None
