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

    # Auth
    auth_mode: str = Field(default="dev-bypass", alias="AUTH_MODE")
    clerk_secret_key: str = Field(default="", alias="CLERK_SECRET_KEY")

    # LLM providers (ADR-0008). Agent-runtime + judge providers routed independently.
    llm_provider: str = Field(default="stub", alias="LLM_PROVIDER")  # stub|ollama|anthropic
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

    # Signing
    hsm_provider: str = Field(default="stub", alias="HSM_PROVIDER")
    simforge_root_key_id: str = Field(default="dev-root", alias="SIMFORGE_ROOT_KEY_ID")
    simforge_signing_private_key_path: str = Field(
        default="./signing-keys/dev-ed25519.pem", alias="SIMFORGE_SIGNING_PRIVATE_KEY_PATH"
    )

    # Certification (dev relaxes the prod 18-scenario battery minimum)
    cert_min_battery_size: int = Field(default=1, alias="CERT_MIN_BATTERY_SIZE")
    cert_validity_days: int = Field(default=90, alias="CERT_VALIDITY_DAYS")

    # Packs
    packs_root: str = Field(default="./packs", alias="PACKS_ROOT")

    # Gap routing (empty in dev → no Linear posting)
    linear_api_key: str = Field(default="", alias="LINEAR_API_KEY")

    # Evidence storage (dev = local filesystem)
    evidence_local_path: str = Field(default="./evidence-local", alias="EVIDENCE_LOCAL_PATH")

    # Budget
    simforge_budget_sandbox_monthly_usd: float = Field(
        default=50.0, alias="SIMFORGE_BUDGET_SANDBOX_MONTHLY_USD"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

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
