from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ownyourcode.modules.authentication.models import User


def resolve_internal_user(session: Session, auth_subject: str) -> User:
    """Create or reuse a user safely across concurrent first requests."""

    with session.begin():
        session.execute(
            insert(User)
            .values(
                id=uuid4(),
                auth_subject=auth_subject,
            )
            .on_conflict_do_nothing(index_elements=[User.auth_subject])
        )
        user = session.scalar(
            select(User).where(User.auth_subject == auth_subject)
        )
        if user is None:
            raise RuntimeError("The authenticated user could not be resolved")
        return user
