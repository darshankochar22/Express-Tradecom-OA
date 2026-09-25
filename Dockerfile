FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/health', timeout=2)" || exit 1

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-2} --access-logfile - wsgi:app"]
