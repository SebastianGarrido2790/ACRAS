# =============================================================================
# Stage 1 — Builder
# =============================================================================
# Installs dependencies into a reproducible layer; no source code yet.
FROM python:3.12-slim AS builder

# Install uv into the builder stage
RUN pip install --no-cache-dir uv==0.8.11

WORKDIR /app

# Copy only the dependency manifest files — not source code.
# Cache this layer; only re-runs when pyproject.toml or uv.lock change.
COPY pyproject.toml ./
COPY uv.lock* ./

# Create the virtual environment and install ONLY lean serving runtime deps (no dev, no training group).
RUN uv sync --no-default-groups --frozen --no-install-project

# =============================================================================
# Stage 2 — Runtime (Lean Serving Container)
# =============================================================================
FROM python:3.12-slim AS runtime

# Non-root user for runtime (defense-in-depth; matches Docker CIS benchmark)
RUN groupadd --gid 1001 acras && \
    useradd --uid 1001 --gid acras --shell /bin/bash --create-home acras

WORKDIR /app

# Copy the pre-built virtual environment from builder
COPY --from=builder --chown=acras:acras /app/.venv /app/.venv

# Set PATH and Python environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PORT=8000

# Copy application configuration, source code, and artifacts directory
COPY --chown=acras:acras params.yaml /app/params.yaml
COPY --chown=acras:acras src /app/src
COPY --chown=acras:acras artifacts /app/artifacts

USER acras

EXPOSE 8000

# Healthcheck hitting the FastAPI /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run FastAPI serving engine via uvicorn module
CMD ["python", "-m", "uvicorn", "src.tier1_ml.app:app", "--host", "0.0.0.0", "--port", "8000"]


