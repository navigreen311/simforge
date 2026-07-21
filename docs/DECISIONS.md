# SimForge Decision Log (ADRs)

Lightweight architecture decision records. Newest first. The spec wins over the blueprint on philosophy; the blueprint wins on implementation detail.

---

## ADR-0001 — Stub all external systems in local dev
**Status:** Accepted (2026-07-20) · **Context:** v1 foundation.

SimForge orchestrates systems absent from local dev: Village OS filesystem, 6 Forge sandbox APIs, Clerk, HSM, Ollama, Linear, Grafana. Building against them directly would block all local progress.

**Decision:** Local dev runs entirely against **stubs**, all behind clean ports/adapters:
- **HSM** → `StubSigner` (local Ed25519). Staging = YubiHSM, prod = AWS CloudHSM. Never stub in prod.
- **Forges** → local stub servers behind the `ForgeAdapter` ABC; `FORGE_*_SANDBOX_URL` → stubs in dev.
- **Village** → `VILLAGE_DATA_PATH` → a small synthetic fixture tree; fingerprinted for drift.
- **Auth** → `AUTH_MODE=dev-bypass` locally; Clerk in staging/prod.
- **Linear** → empty `LINEAR_API_KEY` = no-op poster in dev.

**Consequence:** the adapter/port boundary must stay clean so real integrations drop in without touching call sites. Contract tests (Phase 9) verify stub ↔ real parity.

## ADR-0002 — Python 3.12 for local dev (blueprint specifies 3.11)
**Status:** Accepted (2026-07-20) · **Context:** only 3.12 and 3.14 are installed; no 3.11.

**Decision:** target **Python 3.12** for `apps/api` + `packages/validator`. 3.12 is close to the blueprint's 3.11, broadly supported by our deps (FastAPI, Pydantic v2, SQLAlchemy, RQ, prisma-client-py), and avoids 3.14 immaturity.
**ASSUMPTION:** no 3.11-only behavior is required. **To change:** install 3.11 and pin via `pyproject.toml` `requires-python`.
**Fact-check:** verify `prisma-client-py` supports 3.12 at pin time; if not, fall back to raw async SQLAlchemy against the same Prisma-migrated schema.

## ADR-0003 — Prisma as schema source of truth for both TS and Python
**Status:** Accepted (from blueprint §A.4).

One `schema.prisma` drives TS (`prisma-client-js`) and Python (`prisma-client-py`). Migrations via Prisma in dev/staging/prod; Alembic reserved for data/backfill migrations Prisma can't express.
**Fact-check:** `prisma-client-py` maturity for async on 3.12; if it blocks, SQLAlchemy models generated/maintained against the same DB — schema.prisma stays canonical.

## ADR-0004 — Vertical-slice build order, spine-first
**Status:** Accepted (2026-07-20).

Prove one scenario → run → score → gate → cert end-to-end (Phases 4–7) before widening to all 15 rubric dims and 6 Forges. Rationale: de-risk the core loop early; avoid large expeditions on unvalidated designs (methodology: don't send Claude to build a poorly-thought-through design at scale).

## ADR-0005 — Monorepo via pnpm workspaces + Turborepo; Python via per-app pyproject
**Status:** Accepted (from blueprint §A.5).

`pnpm-workspace.yaml` + `turbo.json` orchestrate JS packages; `apps/api` and `packages/validator` are standalone Python projects with their own `pyproject.toml` + venv. `scripts/bootstrap.sh` wires both.

---

### Open decisions (to confirm as phases land)
- Scenario-engine branching model (Best-of-N in Phase 4).
- Rubric aggregation weighting (Phase 5) — confirm against spec rubric profile.
- Evidence storage local adapter shape vs. S3 (Phase 7).
