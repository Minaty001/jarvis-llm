# ── JARVIS Backend - Production Dockerfile ──
# Multi-stage build for minimal image size

# ── Stage 1: Dependencies ──
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies system-wide (no --user to avoid permission issues)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──
FROM python:3.11-slim

WORKDIR /app

# Install runtime system dependencies (Postgres client for psycopg2)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy system-wide installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs && \
    chmod -R 755 /app/logs

# Run as non-root user
RUN useradd -m -u 1000 jarvis && \
    chown -R jarvis:jarvis /app
USER jarvis

# Health check (uses PORT env var fallback)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os; import httpx; httpx.get(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/api/health', timeout=5)"

EXPOSE 8000

# Run with uvicorn using PORT env var (Render sets this) with 8000 as fallback
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4
