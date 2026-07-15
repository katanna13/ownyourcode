from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ownyourcode.core.config import get_settings

settings = get_settings()

# Creating an engine does not connect to PostgreSQL. No schema or persistence
# behavior is introduced in Phase 1.
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
