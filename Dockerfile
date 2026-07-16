# =============================================================================
# Harvest Agent — Multi-stage Docker build
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Base image with system deps shared by dev and production
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS base

# Prevent Python from buffering stdout/stderr (useful for logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps needed by scrapling / playwright / networking
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
        libffi-dev \
        libxml2-dev \
        libxslt1-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Stage 2: Dev image — includes test and lint tooling
# ---------------------------------------------------------------------------
FROM base AS dev

WORKDIR /app

# Install dev / test dependencies first (layer caching)
RUN pip install \
    pytest \
    pytest-asyncio \
    pytest-cov \
    httpx \
    click

# Copy full project
COPY pyproject.toml README.md ./
COPY harvest/ harvest/
COPY tests/ tests/

# Install the package in editable mode with all optional deps except heavy ML
RUN pip install -e ".[rich,server]"

# Default: run the test suite
CMD ["pytest", "tests/", "-v", "--tb=short"]

# ---------------------------------------------------------------------------
# Stage 3: Production image — runtime only, minimal attack surface
# ---------------------------------------------------------------------------
FROM base AS production

# Create non-root user
RUN groupadd -r harvest && useradd -r -g harvest -d /app -s /sbin/nologin harvest

WORKDIR /app

# Copy only what's needed from build context
COPY pyproject.toml README.md ./
COPY harvest/ harvest/

# Install production dependencies only
RUN pip install . && \
    # Remove build tools no longer needed at runtime
    apt-get purge -y --auto-remove gcc && \
    rm -rf /var/lib/apt/lists/*

# Persistent cache volume
VOLUME /app/.harvest-cache

# Ensure cache dir exists and is owned by harvest user
RUN mkdir -p /app/.harvest-cache && chown -R harvest:harvest /app/.harvest-cache

USER harvest

# Healthcheck — verify the CLI responds (exits 0) or the process is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "from harvest.cli import main; print('ok')" || exit 1

ENTRYPOINT ["python", "-m", "harvest.cli"]
CMD ["--help"]
