FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Use requirements-dev.txt (adds the test tools) for local development.
ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS}

COPY . .

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000
# Production default: no auto-reload and no migrations at start-up. Migrations
# are a deliberate release step: `alembic upgrade head` (see docs/DEPLOYMENT.md).
# Exec form so the server receives SIGTERM directly and shuts down gracefully.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--timeout-graceful-shutdown", "20", "--no-server-header"]
