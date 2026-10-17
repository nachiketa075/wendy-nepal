FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Dependencies come from the generated lockfiles (exact versions + hashes).
# requirements.txt = runtime only; requirements-dev.txt adds the test tools.
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
# --require-hashes refuses anything not pinned and hashed in the lockfile, so a
# build cannot silently pick up a different or tampered release.
RUN pip install --no-cache-dir --require-hashes -r ${REQUIREMENTS}

COPY . .

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
# Production default: no auto-reload and no migrations at start-up. Migrations
# are a deliberate release step: `alembic upgrade head` (see docs/DEPLOYMENT.md).
# Exec form so the server receives SIGTERM directly and shuts down gracefully.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-graceful-shutdown", "20", "--no-server-header"]
