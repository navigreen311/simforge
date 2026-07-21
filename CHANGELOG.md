# Changelog

All notable changes to SimForge. Format: [Keep a Changelog](https://keepachangelog.com/); this project uses SemVer.

## [Unreleased]

### Added — Agent training loop — approval-gated, re-certifying (v1.1, ADR-0026)
- **Agent training** (`services/training/`) — closes the certifier → *improver* loop. `analyze_run_for_training` reads a run's scorecard; if an **LLM-judge** dim (P7/C1/C2 — what a prompt can move) is below 0.60 it generates a **`TrainingProposal`** (weak dims + a targeted prompt refinement + a bumped prompt version). **Never auto-applied** (`autoApplied` always false).
- **Approval promotes + re-certifies** — `approve_proposal` promotes the agent's prompt version and **suspends every active cert pinned to the old prompt version** (reuses the drift/amendment auto-suspend), so those certs must be reinstated (re-certified, ADR-0020) against the improved prompt; the PDP denies them until then + a `simforge:revocations` event invalidates PEP caches. An improvement can't silently bypass governance.
- **API** `/api/training` — `POST /proposals/from-run/{run}` (null if the run scored well), `GET /proposals` (list/filter), `POST /proposals/{id}/approve|reject` (admin). New `TrainingProposal` table (Prisma + SQLAlchemy).
- **Tests:** +4 (279 api) — version-bump, a good run yields no proposal, and end-to-end: weak run → proposal (weak_dims `[p7_cx]`, prompt.v1→v2) → approve → the pinned cert **suspends** and the **PDP denies it** (`cert_suspended`); reject is terminal. ruff + mypy clean on touched files.

### Added — Integrated (write-enabled) execution — PDP-gated, off by default (v1.1, ADR-0025)
- **Integrated execution** (`services/execution/`) — a run can now *commit* an agent's actions, not just simulate them. **Deliberately relaxes the sandbox-only guardrail (ADR-0001)** for this feature, with safety by construction:
  - **Triple-gated, off by default** — executes only when `INTEGRATED_EXECUTION_ENABLED` (default false) AND the pack's `integratedRunsAllowed` AND the run's `?integrated=true`. Any gate unmet → sandbox. CI runs entirely flag-off; the shipped default changes nothing.
  - **PDP-gated per action** — each tested capability goes through `PDP.decide` (ADR-0024); only an `allow` is **applied**, everything else is **blocked**. An uncertified / suspended / revoked / low-autonomy agent cannot execute.
  - **VillageData fixture never written** — effects are an auditable `TraceEvent` ledger (`integrated_action`/`integrated_revert`), queryable + **reversible** (compensating entries).
- **API** `/api/execution` — `GET /status` (is it enabled), `GET /run/{id}/actions` (the ledger with PDP reasons + revert status), `POST /run/{id}/actions/{id}/revert` (admin). `POST /api/scenarios/{id}/run?integrated=true` requests integrated mode.
- **Tests:** +9 (275 api) — the triple gate (off by default), and end-to-end: a certified L5 agent's cap → **applied**, its uncertified cap → **blocked**, in one run; revert an applied action; can't revert a blocked one. ruff + mypy clean.

### Added — PDP/PEP docs + runbook (v1.1, ADR-0024) — **series complete**
- **`docs/pdp-pep.md`** — operator/architecture doc: the decision matrix, the PEP embed pattern, real-time revocation, graceful degradation, metrics, and a try-it recipe.
- **Runbook R-003** (PDP latency spike / PEP degradation) rewritten to reference the real implementation — the `/metrics` names, the two indexed DB reads on the decide path, revocation-storm diagnosis, and "degradation is safe" guidance.
- ADR-0024 marked complete: the §F.6 spec is fully implemented across the four PDP/PEP PRs (engine + API + metrics, Redis pub/sub, PEP SDK, docs), verified live end-to-end.

### Added — PEP SDK: enforcement cache + graceful degradation (v1.1, ADR-0024)
- **PEP SDK** (`services/pep/`) — the client-side enforcement point a Village runtime or Forge service embeds. `Pep.authorize(req)` calls the PDP once, **caches** the decision for its `ttl_seconds` (bounded by `max_ttl`), and serves the cache until it expires or a revocation event invalidates it. Sets the `simforge_pdp_cache_hit_ratio` gauge.
- **Decision sources** — `HttpDecisionSource` (POST `/api/pdp/decide`, injectable transport) for a remote PEP; `local_decision_source` (in-process PDP + session) for a co-located one.
- **Revocation subscriber** (`subscriber.py`) — `listen_for_revocations(pep)` subscribes to `simforge:revocations` and invalidates matching cache entries in real time.
- **Graceful degradation** (§J.6) — if the PDP is unreachable the PEP serves the **last-known** decision (a Village keeps operating at its last-certified level); after a sustained outage (default **24h**) it downgrades any cached `allow` to `step_up_approval_required`; with no cached decision it applies the action's fail policy (default **fail-closed → deny**).
- **Tests:** +12 (266 api) — cache hit/miss, TTL expiry + cap, invalidate, last-known/24h-downgrade/fail-closed degradation, recovery, event parsing (unit) + HTTP-source enforcement + caching + invalidation against the app (integration). ruff + mypy clean.
- **Verified live** (Postgres 17 + Memurai, `scripts/pdp-pep-demo.py`): PEP authorizes (`downgrade_and_retry`, cache hit 0.50) → cert revoked → API publishes to `simforge:revocations` → subscriber **invalidates the PEP cache in real time (entries→0)** → next authorize `deny/cert_revoked`. **PASS.**

### Added — PDP/PEP: real-time revocation pub/sub (v1.1, ADR-0024)
- **Revocation publisher** (`services/governance/revocation.py`) — publishes cert lifecycle events (`revoked`/`suspended`/`reinstated`) to the Redis channel `simforge:revocations` (§F.4), so PEPs can invalidate their decision caches fleet-wide in ~real time instead of at TTL expiry. **Best-effort**: a down/absent Redis never fails the cert operation (short connect timeout, swallow + log). Publish-only, sandbox-safe.
- **Hooked into the cert lifecycle** — `revoke_agent_cert` → `revoked`; `reinstate_agent_cert` → `reinstated`; Drift Canary suspend → `suspended` (per drifted cert); amendment ratify → `suspended` (per affected cert).
- **Tests:** +4 (254 api) — event payload, publish success (mocked), failure-is-swallowed, and a Memurai-guarded real pub/sub roundtrip (skips when Redis is unreachable, so CI is unaffected). ruff + mypy clean.
- **Verified live:** `publish_cert_event` → live Memurai `simforge:revocations` → subscriber received the exact `{agent_id, forge_cap, event, ts}` event. (Dev note: on Windows use `REDIS_URL=redis://127.0.0.1:...` — `localhost` resolves to IPv6 `::1` for the async client while Memurai binds IPv4.)

### Added — PDP: runtime authorization from certs (v1.1, ADR-0024)
- **Policy Decision Point** (`services/governance/pdp.py`) — `PDP.decide(session, AuthRequest) → AuthDecision`, turning issued certs into runtime enforcement. Decision from the agent's cert-for-the-action + autonomy ladder + safe-mode: safe-mode → step_up; no/suspended/revoked/expired cert → deny (specific reason code); active cert L4/L5 → **allow**, L3 → **step_up_approval_required**, L2 → **downgrade_and_retry** (draft only), L1 → **deny** (observe only). Per-decision `ttl_seconds` for PEP caching; `fail_policy` (default **fail-closed**) for PEP outage behavior.
- **API** `/api/pdp` — `POST /decide` (PEP call, read-only) + `GET /agent/{id}/effective` (a decision per cert, for dashboards/audit).
- **Metrics** — `simforge_pdp_decision_latency_seconds{decision}` + `simforge_pdp_decisions_total{decision,reason_code}` (+ a `simforge_pdp_cache_hit_ratio` gauge for the PEP).
- **Tests:** +16 (251 api) — the full cert × autonomy × safe-mode decision matrix (unit) + the API against real cert issuance/revocation and the effective-permissions view (integration). ruff + mypy clean on touched files.
- First of the PDP/PEP series (ADR-0024); Redis revocation pub/sub + the PEP SDK follow. Read-only, sandbox-safe — no Village writes, no integrated execution.

### Added — Real LLM-judge activation (Ollama) + first-signal report (v1.1, ADR-0023)
- **`auto` provider mode** — `LLM_JUDGE_PROVIDER=auto` (and `LLM_PROVIDER=auto`) resolves to the Ollama judge when `OLLAMA_BASE_URL` answers `GET /api/tags`, else StubProvider. Cached per-process reachability probe that only runs on the `auto` path; **defaults unchanged (`stub`)** so CI stays hermetic + offline. `resolve_provider()` + `reset_reachability_cache()`.
- **Committed real-judge cache** — the 9 canonical scenarios (now spanning all 3 packs incl. new CareGrid `cg_*`) scored once against a live `llama3.1:8b`; entries in `tests/fixtures/llm_cache/` (+27). CI replays them in `replay_strict` with **no live model** via a new offline test (`test_cached_llm_judge_replay.py`), so the real-judge path is exercised in CI.
- **First-signal report** — `docs/calibration/first-real-signal-2026-07-21.md` + `scripts/first-real-signal.py`: stub-vs-Ollama delta (identical inputs) + temperature-0 calibration (3 runs/scenario, mean/stddev/min/max, stddev>0.1 flags). **Headline: the real judge scored the weak-CX scenario P7=0.20 vs stub's blind 0.93 (Δ −0.73); all dims stddev 0.000 at temp 0 → 0 flags.**
- **Tests:** +18 (235 api + 9 validator) — auto-provider resolution/dispatch/guards (8) + canonical-scenario cache replay incl. weak-CX assertion (10). ruff + mypy clean on CI-scoped code.
- **Verified:** `LLM_JUDGE_PROVIDER=ollama` + `LLM_CACHE_MODE=replay_strict` pytest passes from committed cache (no live Ollama); `LLM_JUDGE_PROVIDER=stub` full suite green. Rollback is config-only (unset → stub). Guardrails preserved: sandbox-only, no Village writes, no integrated execution; Constitution/Pack-schema/jurisdiction untouched. ADR-0023.

### Added — CareGrid venture Pack (California home-health staffing) (content)
- **`pack.caregrid.v1`** — a third venture Pack (after greenstone + medlink-pro) exercising the platform across a new domain and **jurisdiction**: California home-health staffing (PHI). Declares the full US-CA + federal compliance set (`hipaa`, `cdph_ca`, `ccpa`, `oig_sam`, `i9`) — so it validates under the enforced jurisdiction rule (ADR-0021) and showcases the multi-state engine (US-CA, not just NV).
- **3 scenarios** spanning four real Forges: `scn.cg.cred.001` (F — VAF license retrieval + medlink-pro credential check), `scn.cg.place.002` (I — medlink-pro shift-fill + funnelforge sequence), `scn.cg.audit.003` (AC — a CDPH surprise audit exercising medlink-pro + VAF + VoiceForge in one run).
- **Tests:** +4 (217 api + 9 validator) — CareGrid validates (multi-state CA), the crisis run emits three Forge faults → three Software Gaps, the placement run passes + scores, and the pack reports satisfied US-CA/US-FED coverage.
- **Verified live (Postgres 17):** CareGrid ingests; `scn.cg.audit.003` → `medlink-pro/compliance` + `vaf/doc_vault` + `voiceforge/call_center` P0 faults; pack coverage satisfied `[US-FED, US-CA]`.

### Added — YubiHSM / CloudHSM signer providers (v1.1)
- **Backend-agnostic HSM signer** (`services/cert/hsm_signer.py`) — `HsmEd25519Signer(Signer)` holds no private key: it delegates `sign` to an on-device `HsmBackend` and derives verify/public-key/key-id from the backend's public key. Every HSM shares this one class.
- **`HsmBackend` protocol** (`sign` + `public_key_der`) with concrete lazy-SDK backends: `_YubiHsmBackend` (the `yubihsm` SDK — connector→session→on-device Ed25519 `sign_eddsa`) and `_Pkcs11Backend` (the `pkcs11` SDK/vendor `.so` — EDDSA sign, for AWS CloudHSM or any PKCS#11 HSM). Each raises a clear `SignerConfigError` naming the missing SDK/config instead of crashing.
- **Dispatch** — `get_signer` resolves `HSM_PROVIDER=yubihsm|cloudhsm` to these builders (stub/file unchanged); a genuinely unknown provider still raises `NotImplementedError`. Optional deps under the `hsm` extra (`yubihsm[http]`, `python-pkcs11`) — **not** pulled by dev/CI. Config: `YUBIHSM_*` / `PKCS11_*`.
- **Tests:** +6 (214 api + 8 validator) — shared signer sign/verify/public-key/key-id round-trip via a fake Ed25519 backend, non-Ed25519-key rejection, and dispatch/SDK-missing guards for both providers. ruff + mypy clean on touched files.
- **Boundary (honest):** the shared crypto logic + dispatch/guards are unit-tested; the thin per-vendor connection wrappers need real hardware and activate at deploy time (`pip install '.[hsm]'` + a reachable HSM + creds — no code change). ADR-0022.

### Changed — Enforce jurisdiction coverage in the pack validator (v1.1)
- **Jurisdiction registry moved to `validator.jurisdiction`** (single source of truth). The API (which already imports the validator for ingestion) now **re-exports** from it in `services/jurisdiction/{registry,engine}.py`, so the two can't drift.
- **Corrected federal model** — the federal `oig_sam`/`i9`/`hipaa` flags are **PHI-gated** (healthcare-staffing requirements, not universal), so non-healthcare packs (e.g. real-estate greenstone, `phi_required: false`) aren't forced to declare them. State flags stay self-satisfying (a state is in scope only because its flag was declared).
- **New validator rule** `jurisdiction_under_declared` — a pack that declares any compliance flags must declare the full set required by its inferred jurisdictions (federal + PHI + each state). A gap is a validation **error** → CLI exits non-zero → the `validate-packs` CI job fails. Moves the Jurisdiction Engine from advisory (ADR-0019) to **enforced**.
- **Tests:** +3 validator (8 total) — under-declared PHI pack fails, fully-declared passes, non-PHI pack not forced; +existing greenstone/medlink still valid. API jurisdiction tests updated for the PHI-gated model (208 api). ruff + mypy clean on touched files.
- **Verified:** validator CLI passes greenstone + medlink-pro (exit 0), fails an under-declared PHI pack (`jurisdiction_under_declared`, exit 1). ADR-0021.

### Added — Reinstate a suspended cert by re-certification (v1.1)
- **`reinstate_agent_cert`** — recovers a **suspended** cert (from drift or a constitution amendment) by re-certifying against the *current* version matrix: validate a fresh passing battery → build + sign a new CertSnapshot pinning the now-current Forge/constitution versions → flip the existing cert row to `active` (fresh validity, cleared revocation) → `reinstated` lifecycle event → restore one autonomy level. Updates in place, respecting `UNIQUE(agentId, forgeCap)` (the reason suspended certs must be reinstated, not re-issued). Closes the recovery gap the Drift Canary (ADR-0017) left open.
- **Shared `_create_snapshot` helper** — `issue` + `reinstate` build/sign snapshots through one path → byte-identical canonical/signed payloads (ADR-0007).
- **Deterministic re-issue rejection** — `issue` now rejects when an active **or suspended** cert occupies the pair (was: active only), with a "reinstate/revoke instead" message — consistent on SQLite (tests) and Postgres (was previously an undeclared-constraint gap that let SQLite create a duplicate).
- **Router** `POST /api/certs/agent/{cert_id}/reinstate` (admin) → `IssueCertResponse`.
- **Tests:** +2 (208 api + 5 validator) — drift→suspend→reinstate→active+autonomy-restored+signature-verifies, and reinstate-rejects-non-suspended. Existing cert/drift/governance suites still green (refactor behavior-preserving). ruff + mypy clean on touched files.
- ADR-0020.

### Added — Jurisdiction Engine: NV-only → multi-state (v1.1)
- **Jurisdiction registry** (`services/jurisdiction/registry.py`) — `Jurisdiction` (code/name/level/regulators/required_flags/phi_flags) per authority. **US-FED** federal baseline (`oig_sam`, `i9`; `hipaa` under PHI) applies everywhere; six states (NV/CA/TX/FL/AZ/NY) layer their regulator + required flags. Reverse flag→jurisdiction index for inference. Adding a state = one row.
- **Engine** (`services/jurisdiction/engine.py`) — `resolve_requirements(codes, phi_required)` (federal always included), `infer_jurisdictions(flags)` (reverse-map declared flags → jurisdictions), `coverage_for_flags(...)` → `CoverageReport` (required/present/missing/extra + `satisfied`); multi-state via explicit codes; unknown code → `UnknownJurisdictionError` (404).
- **Router** `/api/jurisdictions` — list, `{code}/requirements`, `POST /coverage`, and `GET /coverage/pack/{pack_id}` (infer a pack's jurisdictions from its `complianceFlags`+`phiRequired` and report gaps). No Prisma/pack-schema change.
- **Tests:** +14 (206 api + 5 validator) — federal baseline, NV/CA/multi-state requirements, inference, coverage satisfied/missing/extra, unknown→raise, and the router incl. real-pack coverage. ruff + mypy clean on touched files.
- **Verified live (Postgres 17):** 7 jurisdictions (was NV-only); `pack.medlink-pro.v1` → satisfied `[US-FED, US-NV]`; NV-only flags → missing `[oig_sam, i9, hipaa]`; NV+CA additionally requires `cdph_ca`+`ccpa`. ADR-0019.

### Added — Real Clerk JWT auth + production Ed25519 signer (v1.1)
- **Real Clerk verification** (`AUTH_MODE=clerk`) — `auth/clerk.py` verifies a real Clerk RS256 JWT (PyJWT + cryptography; added dep `pyjwt[crypto]`): Bearer parse → resolve signing key → verify signature + `exp`/`iat` (+ optional `iss`/`aud`). Key from `CLERK_JWKS_JSON` (static, offline/test) or `CLERK_JWKS_URL` (live JWKS, cached). `auth/roles.py` maps `roles`/`public_metadata.roles`/`org_role` claims → SimForge roles. `get_current_principal` dispatches on `AUTH_MODE` (dev-bypass default unchanged); `require_role`/call sites untouched.
- **Production signer** (`HSM_PROVIDER=file`) — `FileEd25519Signer` loads an **existing** Ed25519 key from a secret-injected PEM (`SIMFORGE_SIGNING_PRIVATE_KEY_PEM`) or a path and **never auto-generates** (raises `SignerConfigError` if absent), so a misconfigured prod deploy fails loudly instead of minting an untrusted key. `get_signer` dispatches on `HSM_PROVIDER` (stub|file|yubihsm|cloudhsm); yubihsm/cloudhsm still raise (need vendor SDK + creds). `reset_signer_cache()` for tests.
- Defaults unchanged (`AUTH_MODE=dev-bypass` + `HSM_PROVIDER=stub`) → dev/CI stay offline + deterministic.
- **Tests:** +10 (192 api + 5 validator) — Clerk verify (valid token→principal+roles, expired/wrong-issuer/unknown-key/malformed→401, role-claim shapes) + prod signer (injected-PEM round-trip, require-existing-key, `get_signer` file dispatch, unknown-provider raises). ruff + mypy clean on touched files.
- **Verified live:** `AUTH_MODE=clerk` app → no/garbage token 401, valid self-issued RS256 token 200. ADR-0018.

### Added — Drift Canary: Forge version drift → auto-suspend (v1.1)
- **Real Forge-version pin at issuance** — `issue_agent_cert` now pins `forge_versions={forge: await get_current_version()}` (was the placeholder `"sandbox.dev"`), so a cert is bound to the actual Forge version its battery ran against. Falls back to `"{forge}.unknown"` if the lookup errors (issuance never fails on a Forge hiccup).
- **Drift Canary** (`services/drift/canary.py`) — `scan_forge_drift` compares every active cert's pinned Forge version against the Forge's current `get_current_version()`; on drift it auto-suspends the cert (status `suspended` + lifecycle event) and defensively demotes the agent one autonomy level, mirroring the constitution-amendment auto-suspend. Versions cached per scan (one hit per Forge). An **unreachable** Forge is reported but never suspended (a transient outage must not knock out certs).
- **Router** `/api/drift` — `GET /status` (viewer, dry-run report) + `POST /scan` (admin, scan + auto-suspend). Composes with ADR-0016: drift is detected against the live HTTP sandbox's version when a forge is in http-mode.
- **Tests:** +4 (182 api + 5 validator) — real-version pin, no-drift-when-matching, and drift→suspend+demote (dry-run reports without acting; scan suspends). ruff + mypy clean on touched files.
- ADR-0017.

### Added — HTTP-backed Forge adapter + real-sandbox swap (post-v1)
- **Uniform `exercise(tenant, cap, fault)` op** on the `ForgeAdapter` contract — every forge (Local or HTTP) is now driven through one method. The scenario runner's six `_run_<forge>` helpers + per-forge fault dicts collapsed into a single `_run_forge_side_effects` loop (group caps by forge → resolve adapter → exercise → trace); the runner's only forge-specific knowledge left is *which* fault to inject (`_FORGE_MODULE_FAULT`/`_FORGE_DEFAULT_FAULT`), not *how* to exercise. No more `cast(LocalX, …)`.
- **`HttpForgeAdapter`** (`services/forges/http_adapter.py`) — implements the full contract against a real sandbox over HTTP (generic sandbox API: health/version/tenants/seed-state/audit-log/faults/exercise). Injectable httpx transport for hermetic tests.
- **Mode selection** (`FORGE_MODE=local|http` + `FORGE_SANDBOX_URLS="name=url,…"`, ADR-0016) — `get_forge_adapter` returns `HttpForgeAdapter` when http-mode + a URL is configured for that forge, else Local. **Per-forge and mixed**: some forges HTTP, others Local, in the same run. Default Local keeps dev/CI deterministic/offline. `local_forge_adapter()` exposes the Local adapter regardless of mode.
- **Reference sandbox** (`services/forges/reference_sandbox.py`) — a conformant FastAPI implementation of the generic sandbox API backed by the Local engine, used to test `HttpForgeAdapter` hermetically (HTTP→engine→HTTP via ASGI transport) and runnable via **`scripts/run-forge-sandbox.py <forge> --port N`**.
- **Tests:** +10 (179 api + 5 validator) — HttpForgeAdapter round-trip vs the reference sandbox (all 6 forges, inject-fault, unreachable→unhealthy) + a runner-over-HTTP integration test (patches the adapter factory so `scn.gs.crisis.003`'s 3-forge fault→gap loop runs over HTTP). ruff + mypy clean on touched files.
- **Verified live:** reference CapitalForge sandbox on `:9101`; main API `FORGE_MODE=http` → `/api/forges/capitalforge/health` crosses HTTP (mode `http`); `scn.gs.buy.002` drove `POST /sandbox/tenants` → `/exercise` → `DELETE` on the sandbox → `capitalforge/emd` fraud_flag → Software Gap, while `cre-forge` (no URL) stayed Local in the same run. ADR-0016. **The real-sandbox swap the six Forge ADRs promised is now real.**

### Added — Sixth (final) real Forge: FunnelForge (Flows) — **all 6 Forges now real** (post-v1)
- **FunnelForge Flows** — deterministic in-process engine (`services/forges/funnel.py`) + `LocalFunnelForgeAdapter` (`funnelforge.py`, version `funnelforge.flows.v1`): tenants, synthetic leads/segments/campaigns/sequences, flow-fault injection + run. Fault menu: delivery/compliance (webhook_dropped/campaign_to_unsubscribed → **P0**), flow/data (sequence_misfire/segment_stale/bounce_unhandled/lead_misattributed → **P1**, duplicate_enrollment → **P2**). Fixtures synthetic only. **Registry now resolves all 6 Forge names to real Local adapters**; `NullForgeAdapter` is retained only as the fallback for unknown forge names.
- **Runner** — `_run_funnelforge` added to the per-forge dispatch with a per-module fault map (`_FUNNEL_FAULT`). Reporter is forge-agnostic, so funnelforge faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`scn.ml.place.002`** now surfaces its `funnelforge.sequences.trigger` cap as a real flow fault → Software Gap.
- **Router** `POST /api/forges/funnelforge/demo`.
- **Tests:** +14 (169 api + 5 validator) — Funnel engine (all 7 fault severities + seed-state), FunnelForge adapter **contract test** (§I.3), all-6-real registry resolution + unknown-name Null fallback, demo, and the funnelforge fault→gap integration on `scn.ml.place.002`. ruff + mypy clean on touched files.
- **Verified live:** `scn.ml.place.002` → `funnelforge/sequences` sequence_misfire fault → Software Gap `funnelforge/sequences`. ADR-0015. **6 of 6 Forges real — the fault→gap loop is complete across the whole Forge surface.**

### Added — Fifth real Forge: medlink-pro (Clinical Console) (post-v1)
- **medlink-pro Clinical Console** — deterministic in-process engine (`services/forges/clinical_console.py`) + `LocalMedLinkProAdapter` (`medlink_pro.py`, version `medlink-pro.console.v1`): tenants, **PHI-synthetic** staffing state (scheduler/compliance/clinician), UI + staffing fault injection + task run. Fault menu: compliance/safety (credential_expired_unflagged/shift_double_booked/phi_overexposure → **P0**), UI/state (ui_blocking_modal/stale_roster/timecard_missing/msa_terms_stale → **P1**). Fixtures synthetic only ("SYNTHETIC CLINICIAN"/"SYNTHETIC FACILITY") — never real PHI. Registry now resolves `medlink-pro` → real adapter.
- **Runner** — `_run_medlink_pro` added to the per-forge dispatch with a per-module fault map (`_CONSOLE_FAULT`: scheduler→shift_double_booked, compliance/clinician→credential_expired_unflagged, else ui_blocking_modal). Reporter is forge-agnostic, so medlink-pro faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`pack.medlink-pro.v1`** staffing scenarios (e.g. `scn.ml.place.002`) now surface real console faults → Software Gaps.
- **Router** `POST /api/forges/medlink-pro/demo`.
- **Tests:** +14 (155 api + 5 validator) — Clinical Console engine (all 7 fault severities + seed-state), medlink-pro adapter **contract test** (§I.3), registry resolution, demo, and the medlink-pro fault→gap integration on `scn.ml.place.002`. ruff + mypy clean on touched files.
- **Verified live:** `scn.ml.place.002` → `medlink-pro/scheduler` shift_double_booked P0 fault → Software Gap `medlink-pro/scheduler`. ADR-0014. **5 of 6 Forges now real** (only funnelforge remains Null).

### Added — Fourth real Forge: CRE Forge (Deal Desk) (post-v1)
- **CRE Forge Deal Desk** — deterministic in-process engine (`services/forges/deal_desk.py`) + `LocalCREForgeAdapter` (`cre_forge.py`, version `cre-forge.dealdesk.v1`): tenants, synthetic CRE deals (assignment/wholesale/double_close/novation, never real party data), deal-fault injection + processing. Fault menu spans deal (title_defect/lien_undisclosed/assignment_blocked/deal_stale), buyer (buyer_unresponsive), lead/sequence (sequence_stall/duplicate_lead). Severities: title_defect/lien_undisclosed/assignment_blocked → **P0**, deal_stale/buyer_unresponsive/sequence_stall → **P1**, duplicate_lead → **P2**. Registry now resolves `cre-forge` → real adapter.
- **Runner** — `_run_cre_forge` added to the per-forge dispatch; injects `title_defect` (P0) on fault — the crisis scenario's premise. Reporter is forge-agnostic, so CRE Forge faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`scn.gs.crisis.003`** now surfaces **all three** of its declared forge faults in one run — a CRE `title_defect`, a VAF `forged_signature`, and a VoiceForge `dropped_call`.
- **Router** `POST /api/forges/cre-forge/demo`.
- **Tests:** +13 (141 api + 5 validator) — Deal Desk engine (all 7 fault severities), CRE Forge adapter **contract test** (§I.3), registry resolution, demo, and the CRE Forge fault→gap integration. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `cre-forge/deals` title_defect P0 fault → Software Gap `cre-forge/deals`. ADR-0013. **4 of 6 Forges now real.**

### Added — Third real Forge: VoiceForge (Call Center) (post-v1)
- **VoiceForge Call Center** — deterministic in-process engine (`services/forges/call_center.py`) + `LocalVoiceForgeAdapter` (`voiceforge.py`, version `voiceforge.callcenter.v1`): tenants, synthetic calls against a persona catalog (§E.2 preload), call-fault injection + handling. Fault menu spans line-quality (dropped_call/dead_air/line_noise), call-flow (misroute/hold_timeout/escalation_failure), and compliance (disclosure_missing). Severities: dropped_call/escalation_failure/disclosure_missing → **P0**, rest → **P1**. Registry now resolves `voiceforge` → real adapter.
- **Runner** — `_run_voiceforge` added to the per-forge dispatch; cap's 3rd segment selects call direction (`voiceforge.call_center.inbound` → inbound). Reporter is forge-agnostic, so VoiceForge faults become real Software Gaps with no reporter change. Sandbox-isolated (no Village writes).
- **`scn.gs.crisis.003`** now surfaces **both** a VAF document fault and a VoiceForge call fault in one run (it already declared `voiceforge.call_center.inbound`).
- **Router** `POST /api/forges/voiceforge/demo`.
- **Tests:** +14 (128 api + 5 validator) — Call Center engine (all 7 fault severities), VoiceForge adapter **contract test** (§I.3), registry resolution, demo, and the VoiceForge fault→gap integration. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `voiceforge/call_center` dropped_call P0 fault → Software Gap `voiceforge/call_center`. ADR-0012. **3 of 6 Forges now real.**

### Added — Second real Forge: VisionAudioForge (VAF) Doc Vault (post-v1)
- **VAF Doc Vault** — deterministic in-process engine (`services/forges/doc_vault.py`) + `LocalVAFAdapter` (`visionaudioforge.py`, version `vaf.docvault.v1`): tenants, **synthetic** document generation (never real PHI), document-fault injection + OCR extraction. Fault menu (§E.3) with severities — forged_signature/revoked_license/oig_match → **P0**, expired_date/name_dob_mismatch/altered_amount → **P1**, missing_pages → **P2**. Registry now resolves `vaf` → real adapter.
- **Runner generalized** — `_run_capitalforge_side_effects` → `_run_forge_side_effects`, dispatching per-forge (CapitalForge + VAF). Fault trigger widened to **`tier == "advanced_crisis"` OR even `seed`**. The reporter's `detect_forge_fault_gaps` is forge-agnostic, so **VAF faults become real Software Gaps** with no reporter change. Sandbox-isolated (no Village writes).
- **Scenario** `scn.gs.crisis.003` gains `vaf.doc_vault.retrieve` — the seeded `david_kim` crisis run surfaces a forged-signature fault on the title document.
- **Router** `POST /api/forges/vaf/demo` — mirrors the CapitalForge demo.
- **Tests:** 9 new (114 api + 5 validator) — Doc Vault engine (all 7 fault severities), VAF adapter **contract test** (§I.3), registry resolution, VAF demo, and the VAF fault→gap integration on `scn.gs.crisis.003`. ruff + mypy clean on touched files.
- **Verified live:** `scn.gs.crisis.003` → `vaf/doc_vault` forged_signature fault → Software Gap `vaf/doc_vault`. ADR-0011.

### Added — First real Forge: CapitalForge (Mock Bank) (post-v1)
- **`ForgeAdapter` contract** (`services/forges/base.py`) — provision/teardown sandbox tenant, seed state, inject fault, audit log, version; `SandboxTenant`/`Fault`/`FaultType`; `NullForgeAdapter` for unwired Forges.
- **CapitalForge = Mock Bank** — deterministic in-process engine (`mock_bank.py`) + `LocalCapitalForgeAdapter`: tenants, accounts, apply/wire/emd_release, fault injection (declination/fraud/nsf/ofac/velocity), audit log. Registry/factory `get_forge_adapter`.
- **Runner wiring** — capitalforge scenarios provision a sandbox tenant, run the tested op, and record `forge_action`/`forge_fault` trace events (sandbox-isolated; deterministic fault on even seed). **Real Software Gaps** now derive from `forge_fault` events (`detect_forge_fault_gaps`), merged with heuristics.
- **Router** `/api/forges` — list/health + CapitalForge demo flow.
- **Tests:** 15 new (100 api + 5 validator) — Mock Bank engine, adapter **contract test** (§I.3), Null adapter, Forge router, and the fault→gap integration. ruff clean.
- **Verified live:** `scn.gs.buy.002` → `emd/fraud_flag` fault → Software Gap `capitalforge/emd`. ADR-0010.

### Added — Real Ollama LLM provider (post-v1)
- **`OllamaProvider`** — real `POST /api/chat` (non-streaming, seeded) against a local Ollama; transcript roles mapped (agent→assistant, scenario/world→user); token accounting from `prompt_eval_count`+`eval_count`.
- **Provider selection** via `LLM_PROVIDER` (`stub` default · `ollama` · `auto` = Ollama-if-reachable-else-stub · `openai`); `OLLAMA_MODEL` (default `llama3.1:8b`). StubProvider stays default so tests/CI remain deterministic (ADR-0008).
- **Script:** `scripts/run-scenario-ollama.py` — drive a scenario with a real model and print the transcript.
- **Tests:** 4 new (74 api total) — role mapping, provider selection, and mocked-HTTP `complete()` request/response parsing. ruff clean.

### Added — Phase 9 (Observability, security & deploy) — **v1 feature-complete**
- **Metrics** (`telemetry/metrics.py`) — real Prometheus collectors (`simforge_runs_total`, `_readiness_gate_total`, `_certs_issued_total`, `_tokens_used_total`, `_run_duration_seconds`, …) exposed at **`/metrics`**; wired into the run + cert flows.
- **Dashboard aggregates** (`/api/dashboard/*`) — `summary`, `throughput` (runs by status + tokens + cost), `readiness-matrix`.
- **Security** — role-based authz already enforced on every endpoint; Clerk JWT verification **seam** (`auth/clerk.py`, gated by `AUTH_MODE`); `docs/security.md` (keys, PHI, secrets, audit).
- **Deploy scaffolding** — Terraform (`infra/terraform/`: rds/redis/s3/ecs/iam), CI (`contract-tests.yml`, `deploy-staging.yml`, `deploy-prod.yml`), `docs/deploy.md`, **7 incident runbooks** (R-001…R-007) + `DR.md` + `KEY_CEREMONY.md`.
- **Tests:** 4 new (70 api + 5 validator) — `/metrics` exposition + dashboard summary/throughput/readiness. ruff clean.

### Added — Phase 8 (Governance & Object Registry / Lineage)
- **Governance** (`services/governance`) — constitution lifecycle + **amendment workflow** (propose → cooling period → ratify/withdraw/veto); ratification bumps the version, supersedes the prior, and **auto-suspends certs pinned to the old constitution**; impact analysis (affected-cert count); in-process **safe-mode** flag.
- **Object Registry + Lineage** (`services/registry`) — URN scheme (`urn:gc:village:<kind>:<id>`), register/resolve/tombstone, directed lineage edges + BFS path + neighborhood subgraph. Cert issuance now **emits lineage** (`produced_by`/`derived_from`/`pinned_to`/`evidenced_by`).
- **Models:** Constitution, ConstitutionalAmendment, ObjectRegistryEntry, LineageEdge.
- **Endpoints:** `/api/constitution/*` (current/version/history/amendments/safe-mode), `/api/registry/*` (urn/kind/register/tombstone), `/api/lineage/*` (from/to/path/subgraph).
- **Frontend:** Constitution + amendments page, Lineage explorer; sidebar enabled. **Script:** `scripts/seed-constitution.py`.
- **Tests:** 7 new (66 api + 5 validator) — URN/lineage path+subgraph, constitution ratify/current, amendment cooling→ratify→supersede, cert-issuance-emits-lineage. ruff clean.
- **Verified live:** amendment ratified → v1.0.0→v1.0.1, 2 dependent certs auto-suspended.

### Added — Phase 7 (Certification, signing & autonomy ladder)
- **Signing** (`services/cert/signer.py`) — `Signer` ABC + Ed25519 **StubSigner** (dev; generates/persists a keypair); HSM providers drop in behind the ABC.
- **CertSnapshot** (`snapshot.py`) — version-pinned payload with a stable canonical encoding; `content_hash` + signature.
- **Registry** (`registry.py`) — `issue_agent_cert` (validates a passing-gate battery, no active duplicate), signs a CertSnapshot, writes an evidence bundle, advances the **Autonomy Ladder** L1→L2; `revoke_agent_cert` (audited, demotes one level).
- **Verifier** (`verifier.py`) — recomputes canonical + checks hash & signature. **Autonomy ladder** state machine (`autonomy_ladder.py`). **Evidence** bundle storage (local FS in dev).
- **Models:** AgentCert, DeptCert, CertSnapshot, CertLifecycleEvent, AutonomyEvent. **Workers:** `cert_lifecycle_worker` (expiry sweep).
- **Endpoints:** `/api/certs/agent/*` (issue/list/detail/revoke), `/api/snapshots/{id}` + `/verify`, `/api/attest/cert/{id}` + `/public-keys`, agent autonomy promote/downgrade/history.
- **Frontend:** Cert Registry + **Readiness Gate Matrix** (agent × Forge-cap grid); sidebar enabled.
- **Tests:** 12 new (59 api + 5 validator) — signer roundtrip/tamper, full issue→verify→autonomy flow, duplicate/failing-battery rejection, revoke-demotes. ruff clean.
- **Verified live:** passing run → signed cert issued, autonomy L1→L2, **signature verifies True against Postgres**, external attestation valid, revoke demotes L2→L1.
- **ADR-0007:** persisted timestamps are **naive UTC truncated to ms** (Prisma `timestamp(3)`); fixed a signature-verification bug where microsecond/tz round-tripping broke the signed hash.

### Added — Phase 6 (Triple Reporter + Gaps)
- **Software Gap detector** (`services/reporter/software_gap.py`) — surfaces Forge defects from run outcome + tier against tested Forge caps (v1 heuristic; real detection reads Forge sandbox error traces).
- **Village-OS Gap detector** (`services/reporter/village_os_gap.py`) — principled CCB-threshold anomalies per framework (ARC fragmentation, high regret, drive imbalance, drift, low valence); healthy agents → no gaps.
- **Reporter service** — dedup-persists gaps (deterministic `SF-GAP-`/`SF-VG-` ticket ids, occurrence counting) + no-op **Linear client** (dev); `reporter_worker` RQ entrypoint; runs auto-emit reports on completion.
- **Models:** `SoftwareGap`, `VillageOSGap`. **Endpoints:** `/api/gaps/software`, `/api/gaps/village-os`, gap detail, status update, `top-10/forge/{forge}`, `top-10/village-os`.
- **Frontend:** Software + Village-OS gap tables (severity pills, occurrence counts) + Top-gaps widget on the overview; sidebar Gaps enabled.
- **Tests:** 12 new (51 api + 5 validator) — detectors (crisis→P1, slo→P0, anomalous CCB→framework gaps, healthy→none), dedup, endpoints. ruff clean.
- **Verified live:** crisis run surfaced 2 P1 software gaps (cre-forge, voiceforge); healthy run → 0 Village-OS gaps.

### Added — Phase 5 (Evaluation engine + Readiness Gate)
- **15-dimension rubric** (`services/evaluation`) — 8 performance (P1–P8) + 7 cognitive (C1–C7) deterministic heuristic scorers over the transcript + CCB pre/post diff + scenario metadata (`dimensions/performance.py`, `dimensions/cognitive.py`); LLM-judge dims (P7/C1/C2) swap in behind the same signatures later.
- **Readiness Gate** (`gate.py`) — hard auto-fails on P2 compliance violation and C4 ARC fragmentation (sudden_shift/regression/fragmentation); otherwise all perf dims must clear the per-tier threshold and the cognitive aggregate its minimum.
- **Regression detector** (`regression.py`) — flags an agent that previously passed a scenario now failing (for Phase 7 revocation + Phase 9 nightly worker).
- **Scorecard model** + `evaluate_run` orchestration (persists 15 dims + gate + turn annotations + remediation recs); runs auto-evaluate on completion; `eval_worker` RQ entrypoint.
- **Endpoint:** `GET /api/runs/{id}/scorecard`.
- **Frontend:** `FifteenDimChart` (perf + cognitive bars, gate badge, C4/compliance callouts, remediation list) on the run detail page.
- **Tests:** 8 new (37 api + 5 validator) — all 15 dims scored, clean run passes, compliance + ARC auto-fails, missing-CCB handling, scorecard endpoint. ruff clean.
- **Verified live:** David Kim's `scn.gs.src.001` run → scorecard persisted, **GATE PASSED** (cognitive aggregate 0.878); a compliance/ARC violation auto-fails (unit-tested).
- Calibrated P7 so a professional stub response clears the bar (coarse under the stub; discriminating with a real LLM-judge).

### Added — Phase 4 (Scenario runner spine)
- **Agent runtime** (`services/agent_runtime`) — 9-layer system-prompt assembly from Village state (resilient to agents missing from the dev tree) + a **deterministic offline `StubProvider`** LLM (ADR-0001 philosophy; Ollama/OpenAI drop in behind the same interface).
- **Scenario engine** (`services/scenario_engine`) — `RunState` + `Phase` state machine (setup→cold_open→turn↔complication→resolution→wrap), `ComplicationInjector`, deterministic via `seed`.
- **Mock world** (`services/mock_world`) — in-process deterministic counter-party persona + Forge action recorder.
- **Runner orchestration** (`services/runner`) — resolves scenario/pack/agent → creates Run → captures CCB pre → runs → persists transcript + TraceEvents + CCB post → sets status; `runner_worker` RQ entrypoint.
- **Models:** `Run`, `TraceEvent` (Prisma-mapped).
- **Endpoints:** `POST /api/scenarios/{id}/run` (inline exec, deterministic) + `/api/runs` (list/detail/transcript/trace).
- **Frontend:** Runs list + Run detail (transcript bubbles with complication highlight + trace timeline) + a client "Run" button on Pack scenarios; sidebar Runs enabled.
- **Fixtures:** Village generator extended to all 8 seeded agents.
- **Tests:** 7 new (30 api + 5 validator) — runner determinism/completion/complication; run endpoint end-to-end, unregistered-agent + missing-scenario 404s. ruff clean.
- **Verified live:** David Kim ran `scn.gs.src.001` → `passed`/`resolved`, complication injected, transcript + trace + CCB pre/post persisted to Postgres.

### Added — Phase 3 (Pack + Scenario ingestion & validation)
- **Validator package** (`packages/validator`) — typed Pack/Scenario YAML schemas, referential + readiness-gate rules, and a **PHI regex guard** (rejects SSN/DOB-shaped tokens). CLI `simforge-validate`. Single source of truth reused by the backend.
- **Sample Packs:** `packs/greenstone/v1` and `packs/medlink-pro/v1` (PHI-required), 3 scenarios each across foundational/intermediate/advanced-crisis tiers.
- **Backend:** Pack/Scenario/ReadinessGate models (`StrArray` = Postgres text[] with SQLite JSON fallback), ingestion service (load → validate → idempotent upsert), routers `/api/packs` (list/detail/ingest/validate/sign) and `/api/scenarios` (list/detail).
- **Frontend:** Packs list + Pack detail pages (scenarios table with tier pills + golden marker); sidebar Packs enabled.
- **CI:** `ci.yml` (validator + api + web jobs) and `pack-validator.yml` (validates `packs/` on PR).
- **Automation:** `scripts/ingest-scenario-library.py` (idempotent bulk ingest).
- **Tests:** 9 new (23 api + 5 validator) — validator happy-path + PHI guard + missing-threshold; ingestion idempotency; packs/scenarios endpoints. All green; ruff clean both packages.
- **Verified live:** both Packs ingested via API into Postgres (2 packs, 6 scenarios, 2 gates); tier filter + detail confirmed.

### Added — Phase 2 (Village reader + CCB)
- **Village reader** (`services/village/reader.py`) — read-only getters for all 10 frameworks (game, mate, soul, breath, fot, hfm, arc, echo, drift, ame) + episodes + identity, plus a structural **schema fingerprint** with drift detection (`verify_fingerprint`).
- **CCB composer** (`services/village/ccb_composer.py`) — assembles the 10 frameworks into a snapshot with a deterministic SHA-256 content hash; persistence via `ccb_store.py`.
- **Fingerprint capture** (`services/village/fingerprint.py`) + `fingerprint_worker` (RQ) + self-contained CLI `scripts/check-village-fingerprint.py`.
- **Models:** `CCB`, `VillageFingerprint` (mapped to Prisma tables; JSON framework columns).
- **Endpoints:** `POST /api/agents/{id}/ccb/capture`, `GET /api/agents/{id}/ccb/latest`; `GET /api/health/village-fingerprint` now uses the live reader.
- **Fixtures:** `scripts/make-village-fixture.py` generates a synthetic VillageData tree (2 agents); committed test fixture under `apps/api/tests/fixtures/village/`.
- **Tests:** 10 new (19 total) — reader completeness, fingerprint determinism/mismatch, CCB composer determinism, capture→latest endpoints, fingerprint capture. ruff clean.
- **Verified live:** CCB captured for `taylor_zhang` → persisted to Postgres; fingerprint `9fa4eecd…` served.
- **Decision:** ADR-0006 (Village path conventions are dev conventions pending reconciliation) + Windows dev-server kill-by-port gotcha.

### Added — Phase 1 (runnable skeleton)
- **Backend (`apps/api`):** FastAPI app factory + `config.py` (typed settings) + async SQLAlchemy engine (ADR-0003). Routers: `/api/health` (`/`, `/ready`, `/village-fingerprint`), `/api/agents` (list+filter+detail), `/api/departments`. Dev-bypass auth with role dependencies (`require_role`). Telemetry stubs. SQLAlchemy models (Agent, Department) mapped to Prisma tables. 9 pytest passing.
- **Frontend (`apps/web`):** Next.js 14 App Router shell (sidebar + live-status header), gold-on-ink design tokens (Tailwind), typed API client, marketing landing (`/`) + overview dashboard (`/dashboard`) rendering live agents/departments from the API. Typecheck + build + lint clean.
- **DB:** first Prisma migration (`init`) applied to native Postgres 17; dev seed run (13 departments, 8 agents).
- **Verified:** full-stack demo — `/dashboard` renders seeded agents live from FastAPI→Postgres; `/api/health/ready` reports database + redis ok.
- **Decisions:** ADR-0003 (SQLAlchemy async runtime; Prisma = schema/migrations/TS-types), fixed dashboard routing to a real `dashboard/` segment (blueprint §D.2 URLs).

### Added — Phase 0 (foundation)
- **Phase 0 — Foundation.** Monorepo skeleton (pnpm + Turborepo), git repo + `navigreen311/simforge` remote.
- `CLAUDE.md` (persona, recipe, quality gates, SimForge context) and 5 Claude commands (`impl-feature`, `test-suite`, `deploy-prod`, `code-review`, `api-test`).
- Complete Prisma schema — 17 entities (`packages/db/schema.prisma`) + dev seed skeleton (13 departments, 8 agents).
- `docker-compose.yml` (Postgres 15 + Redis 7 + optional Ollama), `.env.example`, `.gitattributes` (LF normalization).
- Docs: `SIMFORGE.md`, `BLUEPRINT.md`, `SPEC.md` pointer, `ROADMAP.md`, `DECISIONS.md` (ADR-0001…0005), `CONTRIBUTING.md`, `CONSTITUTION_v1.0.0.yml`.
- `scripts/bootstrap.sh`, `scripts/smoke-test.sh`.
