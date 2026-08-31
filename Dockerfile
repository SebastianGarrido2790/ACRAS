# =============================================================================
# Stage 1 — Builder
# =============================================================================
# Installs dependencies into a reproducible layer; no source code yet.
FROM python:3.12-slim AS builder

# Install uv into the builder stage
RUN pip install --no-cache-dir uv==0.8.11

WORKDIR /build

# Copy only the dependency manifest files — not source code.
# Cache this layer; only re-runs when pyproject.toml or uv.lock change.
COPY pyproject.toml ./
COPY uv.lock* ./

# Create the virtual environment and install runtime deps (no dev extras).
RUN uv sync --no-dev --frozen --no-install-project

# =============================================================================
# Stage 2 — Runtime
# =============================================================================
FROM python:3.12-slim AS runtime

# Non-root user for runtime (defense-in-depth; matches Docker CIS benchmark)
RUN groupadd --gid 1001 acras && \
    useradd --uid 1001 --gid acras --shell /bin/bash --create-home acras

WORKDIR /app

# Copy the pre-built virtual environment from builder
COPY --from=builder /build/.venv /app/.venv

# Set PATH so the venv's site-packages are used
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

# ----
# NOTE: No application source code is copied in this Phase 0 skeleton.
# Source files are added in later phase-specific image layers.
# ----

USER acras

# Prove Python is importable from the venv; container fails if env is broken
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "--version"]
