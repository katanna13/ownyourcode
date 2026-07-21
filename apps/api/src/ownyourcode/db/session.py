from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ownyourcode.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url)
# Creating an engine does not connect or create tables. Alembic owns schema
# lifecycle; requests and services own transaction boundaries.
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
