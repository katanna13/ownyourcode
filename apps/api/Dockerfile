FROM python:3.12-slim

WORKDIR /app

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/src ./src
COPY apps/api/tests ./tests

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

CMD ["uvicorn", "ownyourcode.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
