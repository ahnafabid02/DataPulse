FROM node:24.13.0-bookworm-slim AS interface
WORKDIR /workspace/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt pyproject.toml ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY --from=interface /workspace/src/datapulse/central/static ./src/datapulse/central/static
COPY migrations ./migrations
COPY alembic.ini ./
RUN python -m pip install --no-cache-dir --no-deps --no-build-isolation . \
    && useradd --create-home --uid 10001 datapulse
USER datapulse
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "datapulse.central.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
