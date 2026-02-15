# ---- Build React Frontend ----
FROM node:22-alpine AS frontend-builder

WORKDIR /frontend
COPY frontend/android-sms-api/package.json frontend/android-sms-api/package-lock.json ./
RUN npm ci
COPY frontend/android-sms-api/ ./
RUN npm run build

# ---- Install Python Dependencies ----
FROM python:3.13-slim-bookworm AS backend-builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ---- Final Runtime Image ----
FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y wget unzip && \
    wget https://dl.google.com/android/repository/platform-tools-latest-linux.zip -O /tmp/adb.zip && \
    unzip /tmp/adb.zip -d /opt/ && \
    rm /tmp/adb.zip && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/platform-tools:${PATH}"

WORKDIR /app

COPY --from=backend-builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY backend/ .

COPY --from=frontend-builder /frontend/dist /app/static

EXPOSE 8000
VOLUME ["/app/data"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]