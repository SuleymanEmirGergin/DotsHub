# syntax=docker/dockerfile:1.7
#
# Pre-triage backend image — multi-stage to keep the runtime layer small
# and avoid shipping build toolchains to prod.
#
# Key choices:
#   - python:3.11-slim as base. 3.11 matches backend-regression CI and
#     the runtime.py type hints (generic `dict[...]`, `list[...]` syntax
#     requires 3.9+, we pin 3.11 for speed + stable supabase client).
#   - non-root user (uid 10001) so a container escape can't write into
#     host-mounted volumes as root.
#   - PRETRIAGE_CONFIG_DIR defaults to /srv/pretriage/config so ops can
#     bind-mount a tenant-scoped config dir without touching code.
#   - Healthcheck hits /health which also verifies Supabase reachability.

# ── Builder: compile deps into a clean site-packages ─────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Build-time deps. psycopg[binary] ships its own libpq, so we only need
# basic compile toolchain for any wheel that doesn't publish a binary
# for slim-bookworm.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt ./
RUN pip install --prefix=/install -r requirements.txt

# Pre-fetch the multilingual-e5-base model + pre-build the disease
# embedding cache so cold starts don't pay HF download (~470MB) or
# corpus encode (~5-10s on CPU). Both artifacts go into stable paths
# (/opt/hf-cache and the corpus cache dir) and are copied into the
# runtime stage.
ENV HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache
RUN PYTHONPATH=/install/lib/python3.11/site-packages \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"
COPY app/ /build/app/
COPY scripts/ /build/scripts/
RUN PYTHONPATH=/install/lib/python3.11/site-packages:/build \
    python /build/scripts/precompute_embeddings.py || \
    echo "precompute_embeddings: skipped (corpus build step optional in this stage)"

# ── Runtime: copy install dir + app, drop privileges ─────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PRETRIAGE_CONFIG_DIR=/srv/pretriage/config \
    PORT=8000

# Minimal runtime libs (libpq for asyncpg, curl for the healthcheck).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --gid 0 --home /app pretriage

COPY --from=builder /install /usr/local

# Pre-fetched HF model cache (multilingual-e5-base) so the runtime
# never has to download from huggingface.co on a cold start.
ENV HF_HOME=/opt/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/opt/hf-cache
COPY --from=builder --chown=10001:0 /opt/hf-cache /opt/hf-cache

WORKDIR /app
# Copy only the app — keep the layer small; the rest of the repo (tests,
# dashboard, mobile) is not needed at runtime.
COPY --chown=10001:0 app/ ./app/

# Config dir mount point — make it writable so tenant catalog writes
# land on a mounted volume, not inside the image layer.
RUN mkdir -p /srv/pretriage/config && chown -R 10001:0 /srv/pretriage

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f "http://localhost:${PORT}/health" || exit 1

# Single-worker default; scale with container replicas, not threads,
# so rate-limit state stays per-instance unless REDIS_URL is set.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips=*"]
