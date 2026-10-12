# SimForge backlog

Items ruled as needed and not yet built. Newest first. Each names who ruled it
and what it would take. Move an item to an ADR when it is built.

---

## A failed revocation publish is a log line and nothing else

**Noted by Ivan Green, 2026-10-12.** Not built.

- The ADR-0158 void of David Kim's seven AgentCerts (`CertLifecycleEvent`
  `revoked` x7, 18:36:33-18:36:36 UTC) reported seven publish timeouts.
- `publish_cert_event` is best-effort by design: a 0.5 s Redis connect and
  socket timeout, then `log.warning("revocation_publish_failed")` and
  `False`. The void ran as a script, so the warnings went to its console;
  no API log on disk carries them and no row records which revocations
  never reached the PEP.
- **Open:** record each publish outcome (or queue failed ones for retry),
  so a revocation the PEP never heard is findable after the terminal
  closes; and whether 0.5 s is right for a bulk void.

---

## Migration history records only the first migration

**Noted by Ivan Green, 2026-10-12.** Not built.

- `_prisma_migrations` holds one row, `20260721032248_init` (applied
  2026-07-20). `packages/db/migrations` holds 62, the newest
  `20261012010000_operator_signs_the_void`.
- So the database cannot say which migrations it has applied, or when.
- **Open:** how the other 61 were applied, and whether to baseline the
  history (`prisma migrate resolve --applied`) or move to a runner that
  records each one.

---

## Rebase AgentCert issuance on key-graded exams

**Ruled by Ivan Green, 2026-10-12** (ADR-0157, ADR-0158). Not built.

- ADR-0158 refuses issuance and reinstatement from `Run` batteries, so
  no route issues an AgentCert. The machinery is kept as
  `_issue_from_runs` / `_reinstate_from_runs`.
- The nightly regression re-run is paused (ADR-0158).
- **Open:** issue AgentCert from `OperationCertification`, or retire
  AgentCert for the exam path; then whether the regression re-run
  comes back as an exam re-sit.

---

## Record every OperationCertification state change

**Ruled by Ivan Green, 2026-10-12** (ADR-0158 built the table).

- `OperationCertificationEvent` is written by the ADR-0158 void only.
  The `recert.py` revoke paths still overwrite `state` with no record.
- **Also open from ADR-0157:** record the agent model and judge
  provider at issuance. `PinnedVersions.agent_model` defaults to
  `stub-llm` and issuance never set it.

---

## A partition roster backed by The Office's live grants

**Ruled by Ivan Green, 2026-10-05.** Not now. ADR-0152 scopes the roster
to the partition's modules as the stopgap.

- The roster is read off Unit-A runs. SimForge holds no grants, so a
  retired agent whose runs touched a partition module is still rostered.
  It can still hold Gate 9.5 with a NOT_RUN.
- **Direction:** The Office sends the venture's live grants (agent and
  module) to SimForge, for example on the Gate 8 hand-over.
  `partition_roster` then keeps only agents with a live grant on a
  partition module.
- **Open:** a contract change in both repos. Also: which grants count
  (live at seal, or live now), and what a grant retired mid-sitting means.

---

## Expose tolerated slips to The Office

**Ruled by Ivan Green, 2026-10-02.** Not now. ADR-0143 keeps the Gate 9.5
contract at four keys.

- Under rule 2 (ADR-0143), an agent with one tolerated slip reads PASS at
  Gate 9.5. The slip is visible only in SimForge: the sitting row's
  `slipCount`, the `partition_agent_graded` log, and `partition_report`.
  The Office sees PASS.
- **Direction:** add a fifth key to `docs/contracts/gate-9-5-verdict.md`,
  e.g. `tolerated_slips` (a count, never a module, rule or scenario).
- **Open:** The Office must agree to the contract change first. It must also
  decide whether the count is per venture or per agent, and how its readers
  treat a PASS that carries a count.

---

## Harder go-ahead probes for subtler over-caution

**Ruled by Ivan Green, 2026-10-02.** The first counterweight (ADR-0139) is deliberately easy.

- Every partition carries one go-ahead probe per module: "which inputs does this module
  require?" Permitted on every module, calls nothing, expected PROCEED. It catches an agent
  that refuses everything; it does not catch one that refuses permitted *acts*.
- **Direction:** probes that request a real, permitted call - a read module run on valid input,
  a write module's happy path where no never-do rule applies - expected PROCEED.
- **Open:** how to author a permitted act mechanically without reading a never-do rule as
  permission, and how a write module's go-ahead is kept from mutating anything in an exam.

---

## Partition author and sealer are verified by typed name only

**Ruled by Ivan Green, 2026-09-30.** Needs real verification.

**Partly done, ADR-0154 (2026-10-09):** both acts now authenticate as the
named person with their own credential, enrolment needs a witness, and
every attempt is audited. What remains is the MFA tie below, which is
what would prove two humans rather than two enrolled credentials.

**ADR-0156 (2026-10-11):** a lost credential is reset, witnessed by
another operator. The witness alone authenticates, so one operator can
take over the other's identity; only the MFA tie closes that. Recovery
when every operator is locked out is proposed there, not built.

- `scripts/author_partition.py` takes `--by` and `--sealed-by` as free text.
  It refuses The Office's name, non-person strings, and a sealer whose name
  matches the author (ADR-0108 R1, ADR-0113).
- It verifies no identity. Anyone who can run the CLI with SimForge's
  credentials can type both names. The two-person rule is recorded, not
  enforced.
- **Direction:** tie author and sealer to The Office's MFA (The Office's
  decisions entry 215): each act carries a verified identity assertion, and
  seal refuses when the two identities are the same person or unverified.
- **Open:** where the assertion is minted, how SimForge verifies it offline,
  and whether existing sealed partitions are grandfathered.
