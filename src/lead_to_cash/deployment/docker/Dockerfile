# Multi-stage production Dockerfile for Lead to Cash Application
# Optimized for rr-kailash.ai production deployment
#
# OPTIMIZATION NOTES (2026-01-20):
# - Dependencies layer is cached separately from source code
# - pyproject.toml changes trigger dependency rebuild
# - Source code changes only rebuild final layers (~30s vs 4m)
# - Pre-built image from GHCR should be used when possible

# ==============================================================================
# Dependencies Stage - Cached unless pyproject.toml changes
# ==============================================================================
FROM python:3.12-slim AS deps

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy ONLY dependency files first (for layer caching)
# This layer is cached unless pyproject.toml or sdk-users dependencies change
COPY pyproject.toml ./
COPY README.md ./

# Copy sdk-users for local dependency resolution
# NOTE: sdk-users changes less frequently than src/lead_to_cash
COPY sdk-users/ ./sdk-users/

# Create minimal src structure for setuptools (just __init__.py)
RUN mkdir -p src/lead_to_cash && \
    echo "__version__ = 'build'" > src/lead_to_cash/__init__.py

# Install dependencies (this layer is cached if pyproject.toml unchanged)
# Install app + all transitive deps required by kailash/kaizen SDK import chains
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    pip install --no-cache-dir \
        psutil>=5.9.0 \
        Pillow>=10.0.0 \
        aiohttp>=3.9.0 \
        cryptography>=42.0.0 \
        PyJWT>=2.8.0 \
        prometheus_client>=0.20.0 \
        opentelemetry-api>=1.20.0 \
        opentelemetry-sdk>=1.20.0 \
        opentelemetry-exporter-otlp>=1.20.0 \
        opentelemetry-exporter-otlp-proto-grpc>=1.20.0 \
        opentelemetry-exporter-otlp-proto-http>=1.20.0

# ==============================================================================
# Build Stage - Only runs when source code changes
# ==============================================================================
FROM deps AS builder

# Build arguments
ARG BUILD_VERSION=latest
ARG BUILD_DATE
ARG BUILD_REVISION

# Install documentation dependencies
RUN pip install --no-cache-dir \
    sphinx>=8.2.3 \
    furo>=2024.8.6 \
    sphinx-copybutton>=0.5.2 \
    sphinx-design>=0.6.0 \
    sphinxcontrib-mermaid>=1.0.0 \
    myst-parser>=4.0.1

# Now copy actual source code (changes frequently, but deps already installed)
COPY src/ ./src/

# Copy documentation source and build (non-fatal: docs failure must not block deployment)
COPY docs/ ./docs/
RUN cd docs && sphinx-build -b html source _build/html || \
    (echo "WARNING: Sphinx docs build failed, creating empty docs dir" && \
     mkdir -p _build/html && echo "<html><body><p>Documentation build pending.</p></body></html>" > _build/html/index.html)

# ==============================================================================
# Production Stage
# ==============================================================================
FROM python:3.12-slim AS production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
# Note: Context is the 'current' directory after deployment with src/ structure
COPY src/lead_to_cash/ ./src/lead_to_cash/
COPY sdk-users/ ./sdk-users/
COPY pyproject.toml ./

# Copy built documentation from builder stage
COPY --from=builder /build/docs/_build/html/ ./docs/_build/html/

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/outputs /app/.matplotlib \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Environment variables
ENV PYTHONPATH=/app/src:/app/sdk-users \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    LOG_LEVEL=INFO \
    HOME=/app \
    MPLCONFIGDIR=/app/.matplotlib

# Labels for metadata
LABEL version="${BUILD_VERSION}" \
      build_date="${BUILD_DATE}" \
      build_revision="${BUILD_REVISION}" \
      maintainer="RRPS Lead to Cash Team" \
      application="lead-to-cash" \
      domain="rr.kailash.ai"

# Default command - uses AsyncLocalRuntime for Docker optimization
CMD ["python", "-m", "uvicorn", "lead_to_cash.core.gateway:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
