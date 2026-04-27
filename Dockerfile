FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System packages: curl for healthcheck only; no shell tools needed at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged user before copying app
RUN groupadd --system app && useradd --system --no-create-home --gid app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY --chown=app:app . .

USER app

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://127.0.0.1:5050/ || exit 1

# Production: gunicorn with 2 workers, 4 threads, bound to all interfaces.
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "--threads", "4", \
     "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
