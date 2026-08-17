FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations

RUN groupadd --system tuesday \
    && useradd --system --gid tuesday --home-dir /app tuesday \
    && mkdir -p /data \
    && chown -R tuesday:tuesday /app /data

ENV TUESDAY_HOST=0.0.0.0 \
    TUESDAY_PORT=8000 \
    TUESDAY_DATA_DIR=/data \
    PORT=10000 \
    PYTHONUNBUFFERED=1

USER tuesday

EXPOSE 10000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl --fail http://127.0.0.1:${PORT:-10000}/health/live || exit 1

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
