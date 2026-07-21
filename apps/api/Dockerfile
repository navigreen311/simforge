# SimForge API — production image (ADR-0030). Multi-stage, non-root, healthchecked.
# Build context = apps/api. Also installs the validator package (a runtime dependency).
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

# Build deps for cryptography/asyncpg wheels (removed in the runtime stage).
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install into an isolated prefix we copy into the runtime image.
COPY apps/api/pyproject.toml apps/api/README.md* ./apps/api/
COPY packages/validator ./packages/validator
COPY apps/api/src ./apps/api/src
RUN pip install --prefix=/install ./packages/validator \
    && pip install --prefix=/install ./apps/api

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Non-root runtime user.
RUN useradd --create-home --uid 10001 simforge

COPY --from=builder /install /usr/local
COPY apps/api/src ./src
COPY packs ./packs
COPY apps/api/tests/fixtures/village ./village-data-local/../tests/fixtures/village

USER simforge
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
    sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/',timeout=2).status==200 else 1)"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
