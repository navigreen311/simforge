"""Pydantic settings — the single typed view of SimForge's environment (blueprint §A.6)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),  # api cwd or repo root
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    # Core datastores
    database_url: str = Field(
        default="postgresql://simforge:simforge@localhost:5432/simforge",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Auth (AUTH_MODE=clerk verifies real Clerk RS256 JWTs; dev-bypass is the local default)
    auth_mode: str = Field(default="dev-bypass", alias="AUTH_MODE")
    clerk_secret_key: str = Field(default="", alias="CLERK_SECRET_KEY")
    clerk_jwks_url: str = Field(default="", alias="CLERK_JWKS_URL")
    # Offline/test override: a JWKS document as JSON (used instead of fetching CLERK_JWKS_URL).
    clerk_jwks_json: str = Field(default="", alias="CLERK_JWKS_JSON")
    clerk_issuer: str = Field(default="", alias="CLERK_ISSUER")
    clerk_audience: str = Field(default="", alias="CLERK_AUDIENCE")

    # LLM providers (ADR-0008). Agent-runtime + judge providers routed independently.
    # stub|ollama|anthropic|auto. `auto` = ollama-if-OLLAMA_BASE_URL-reachable-else-stub (ADR-0023):
    # safe everywhere — real Ollama locally, deterministic StubProvider in CI. Default stays stub so
    # CI is hermetic with no probe; set LLM_JUDGE_PROVIDER=auto for real-signal runs.
    llm_provider: str = Field(default="stub", alias="LLM_PROVIDER")
    llm_judge_provider: str = Field(default="stub", alias="LLM_JUDGE_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_agent_model: str = Field(default="llama3.1:8b", alias="OLLAMA_AGENT_MODEL")
    ollama_judge_model: str = Field(default="llama3.1:8b", alias="OLLAMA_JUDGE_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_agent_model: str = Field(
        default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_AGENT_MODEL"
    )
    anthropic_judge_model: str = Field(
        default="claude-3-5-sonnet-20241022", alias="ANTHROPIC_JUDGE_MODEL"
    )
    llm_request_timeout_seconds: float = Field(default=60.0, alias="LLM_REQUEST_TIMEOUT_SECONDS")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_cache_dir: str = Field(default="./tests/fixtures/llm_cache", alias="LLM_CACHE_DIR")
    # off | read | record | replay_strict (replay_strict = CI/unit default)
    llm_cache_mode: str = Field(default="off", alias="LLM_CACHE_MODE")
    llm_test_mode: bool = Field(default=False, alias="LLM_TEST_MODE")

    # Village coupling
    village_data_path: str = Field(
        default="./village-data-local/VillageData", alias="VILLAGE_DATA_PATH"
    )
    village_db_path: str = Field(default="./village-data-local/village.db", alias="VILLAGE_DB_PATH")
    village_os_version_fingerprint: str = Field(
        default="dev-fingerprint", alias="VILLAGE_OS_VERSION_FINGERPRINT"
    )

    # Signing. stub = dev (auto-generates a local Ed25519 key). file = production Ed25519 that
    # REQUIRES an existing key (never auto-generates) from SIMFORGE_SIGNING_PRIVATE_KEY_PEM (a
    # secret-manager-injected PEM) or SIMFORGE_SIGNING_PRIVATE_KEY_PATH. yubihsm/cloudhsm = real
    # HSMs (need the vendor SDK + credentials; not enabled here).
    hsm_provider: str = Field(default="stub", alias="HSM_PROVIDER")  # stub|file|yubihsm|cloudhsm
    simforge_root_key_id: str = Field(default="dev-root", alias="SIMFORGE_ROOT_KEY_ID")
    simforge_signing_private_key_path: str = Field(
        default="./signing-keys/dev-ed25519.pem", alias="SIMFORGE_SIGNING_PRIVATE_KEY_PATH"
    )
    # Preferred in prod: inject the PEM directly from a secret manager (no key on disk).
    simforge_signing_private_key_pem: str = Field(
        default="", alias="SIMFORGE_SIGNING_PRIVATE_KEY_PEM"
    )
    # YubiHSM (HSM_PROVIDER=yubihsm) — needs the `yubihsm` SDK + a reachable connector.
    yubihsm_connector_url: str = Field(default="", alias="YUBIHSM_CONNECTOR_URL")
    yubihsm_auth_key_id: int = Field(default=1, alias="YUBIHSM_AUTH_KEY_ID")
    yubihsm_password: str = Field(default="", alias="YUBIHSM_PASSWORD")
    yubihsm_signing_key_id: int = Field(default=0, alias="YUBIHSM_SIGNING_KEY_ID")
    # PKCS#11 / AWS CloudHSM (HSM_PROVIDER=cloudhsm) — needs the `pkcs11` SDK + the vendor .so lib.
    pkcs11_lib_path: str = Field(default="", alias="PKCS11_LIB_PATH")
    pkcs11_token_label: str = Field(default="", alias="PKCS11_TOKEN_LABEL")
    pkcs11_pin: str = Field(default="", alias="PKCS11_PIN")
    pkcs11_key_label: str = Field(default="", alias="PKCS11_KEY_LABEL")

    # Certification (dev relaxes the prod 18-scenario battery minimum)
    cert_min_battery_size: int = Field(default=1, alias="CERT_MIN_BATTERY_SIZE")
    cert_validity_days: int = Field(default=90, alias="CERT_VALIDITY_DAYS")

    # Packs
    packs_root: str = Field(default="./packs", alias="PACKS_ROOT")

    # Integrated (write-enabled) execution (ADR-0025). OFF by default: a run may only execute
    # integrated actions when this is true AND the pack allows it AND the run explicitly requests
    # it — and every action is still gated by the PDP (only `allow` decisions are applied). The
    # read-only VillageData fixture is never written; effects are recorded as an auditable ledger.
    integrated_execution_enabled: bool = Field(default=False, alias="INTEGRATED_EXECUTION_ENABLED")

    # Forge sandboxes (ADR-0016). Default "local" = in-process engines (deterministic/offline,
    # keeps CI hermetic). "http" swaps to real HTTP-backed sandboxes for any forge that has a URL
    # configured in FORGE_SANDBOX_URLS (comma-separated "name=url" pairs); forges without a URL
    # stay Local even in http mode.
    forge_mode: str = Field(default="local", alias="FORGE_MODE")  # local | http
    forge_sandbox_urls_raw: str = Field(default="", alias="FORGE_SANDBOX_URLS")
    forge_request_timeout_seconds: float = Field(
        default=30.0, alias="FORGE_REQUEST_TIMEOUT_SECONDS"
    )

    # Gap routing to Linear (ADR-0029). Empty LINEAR_API_KEY → no-op (dev). With a key + team,
    # gaps post real issues via the Linear GraphQL API (best-effort; a Linear outage never blocks
    # gap emission).
    linear_api_key: str = Field(default="", alias="LINEAR_API_KEY")
    linear_team_id: str = Field(default="", alias="LINEAR_TEAM_ID")
    linear_api_url: str = Field(default="https://api.linear.app/graphql", alias="LINEAR_API_URL")

    # Web-search ingestion for the Scenario Bank (ADR-0042). Empty key → the "stub" provider, so the
    # Web ingestion tab honestly reports "not configured" — no fake results and no network in CI.
    # WEB_SEARCH_PROVIDER=tavily + TAVILY_API_KEY=tvly-... activates a live search-and-extract pass.
    # `auto` (default) = tavily-if-TAVILY_API_KEY-set-else-stub, mirroring the LLM `auto` pattern.
    # auto | tavily | stub
    web_search_provider: str = Field(default="auto", alias="WEB_SEARCH_PROVIDER")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")
    tavily_api_url: str = Field(default="https://api.tavily.com/search", alias="TAVILY_API_URL")
    web_search_max_results: int = Field(default=6, alias="WEB_SEARCH_MAX_RESULTS")
    web_search_timeout_seconds: float = Field(default=20.0, alias="WEB_SEARCH_TIMEOUT_SECONDS")

    # Video / YouTube transcript ingestion (ADR-0043, Batch 6). Two independently-gated seams,
    # both default OFF so the Video tab honestly reports "not configured" and CI never hits a net.
    #  - YouTube captions: no API key, but a network fetch → gated on TRANSCRIPT_YOUTUBE_ENABLED.
    #  - Audio-file transcription: TRANSCRIPT_PROVIDER=openai + OPENAI_API_KEY (raw HTTPS, no SDK).
    transcript_youtube_enabled: bool = Field(default=False, alias="TRANSCRIPT_YOUTUBE_ENABLED")
    transcript_provider: str = Field(default="stub", alias="TRANSCRIPT_PROVIDER")  # stub | openai
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_transcribe_model: str = Field(default="whisper-1", alias="OPENAI_TRANSCRIBE_MODEL")
    transcript_timeout_seconds: float = Field(default=120.0, alias="TRANSCRIPT_TIMEOUT_SECONDS")

    # Evidence storage (dev = local filesystem)
    evidence_local_path: str = Field(default="./evidence-local", alias="EVIDENCE_LOCAL_PATH")

    # Budget caps (ADR-0039). Per-calendar-month USD ceilings on metered run cost, enforced before a
    # run starts. Sandbox runs and integrated (write-enabled) runs have separate caps. Stub/local
    # providers are free (cost 0), so caps never trip in dev/CI — they bind once a real metered LLM
    # or Forge is active.
    simforge_budget_sandbox_monthly_usd: float = Field(
        default=50.0, alias="SIMFORGE_BUDGET_SANDBOX_MONTHLY_USD"
    )
    simforge_budget_integrated_monthly_usd: float = Field(
        default=500.0, alias="SIMFORGE_BUDGET_INTEGRATED_MONTHLY_USD"
    )

    # Distributed tracing (OpenTelemetry → OTLP/HTTP → Grafana Tempo; ADR-0031). No-op unless
    # activated: set OTEL_EXPORTER_OTLP_ENDPOINT to a collector to export spans, or
    # OTEL_TRACES_ENABLED=true to build spans locally without exporting. Default off keeps CI
    # hermetic (spans compile to a no-op tracer; no collector dependency).
    otel_traces_enabled: bool = Field(default=False, alias="OTEL_TRACES_ENABLED")
    otel_exporter_otlp_endpoint: str = Field(default="", alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    otel_service_name: str = Field(default="simforge-api", alias="OTEL_SERVICE_NAME")
    otel_sample_ratio: float = Field(default=1.0, alias="OTEL_SAMPLE_RATIO")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    @property
    def forge_sandbox_urls(self) -> dict[str, str]:
        """Parse FORGE_SANDBOX_URLS ('name=url,name=url') into {forge: base_url}."""
        out: dict[str, str] = {}
        for pair in self.forge_sandbox_urls_raw.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            name, url = pair.split("=", 1)
            name, url = name.strip(), url.strip()
            if name and url:
                out[name] = url.rstrip("/")
        return out

    @property
    def sqlalchemy_url(self) -> str:
        """Translate a Prisma-style postgres URL into an asyncpg SQLAlchemy URL."""
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            base = url
        elif url.startswith("postgresql://"):
            base = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            base = url.replace("postgres://", "postgresql+asyncpg://", 1)
        else:
            base = url
        # asyncpg does not accept libpq query params like ?schema=public
        return base.split("?", 1)[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
