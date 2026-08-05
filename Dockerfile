FROM python:3.11-slim

ARG APP_VERSION=1.0.3
LABEL org.opencontainers.image.title="FinOps CCoE Live Reporting" \
            org.opencontainers.image.version=$APP_VERSION \
            org.opencontainers.image.created="2026-08-05"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
        FINOPS_APP_VERSION=$APP_VERSION \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]