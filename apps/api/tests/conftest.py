from __future__ import annotations

import os
from argparse import Namespace
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient

from ownyourcode.core.config import get_settings
from ownyourcode.db.session import get_db_session
from ownyourcode.main import app
from ownyourcode.modules.authentication.dependencies import get_auth_token_verifier
from ownyourcode.modules.authentication.verifier import (
    AuthenticatedSubject,
    TestAuthTokenVerifier,
)


def _require_test_database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise RuntimeError("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    test_url = make_url(value)
    application_url = make_url(get_settings().database_url)
    if test_url == application_url:
        raise RuntimeError("TEST_DATABASE_URL must differ from DATABASE_URL")
    if not test_url.database or "test" not in test_url.database.lower():
        raise RuntimeError("TEST_DATABASE_URL must name an explicitly designated test database")
    return value


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.cmd_opts = Namespace(x=[f"database_url={database_url}"])
    return config


@pytest.fixture(scope="session")
def test_database_url() -> str:
    return _require_test_database_url()


@pytest.fixture(scope="session")
def migrated_test_engine(test_database_url: str):  # type: ignore[no-untyped-def]
    config = _alembic_config(test_database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_engine(test_database_url, poolclass=NullPool)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def test_session_factory(migrated_test_engine):  # type: ignore[no-untyped-def]
    with migrated_test_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE project_learning_progress, project_learning_attempts, "
                "project_learning_content_versions, project_inspection_snapshots, "
                "project_sources, projects, users CASCADE"
            )
        )
    return sessionmaker(
        bind=migrated_test_engine, autoflush=False, expire_on_commit=False
    )


@pytest.fixture
def test_session(test_session_factory) -> Generator[Session, None, None]:  # type: ignore[no-untyped-def]
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def authenticated_client(test_session_factory) -> Generator[TestClient, None, None]:  # type: ignore[no-untyped-def]
    verifier = TestAuthTokenVerifier(
        {
            "alice-token": AuthenticatedSubject("user_alice"),
            "bob-token": AuthenticatedSubject("user_bob"),
        }
    )

    def override_session() -> Generator[Session, None, None]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_auth_token_verifier] = lambda: verifier
    app.dependency_overrides[get_db_session] = override_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
