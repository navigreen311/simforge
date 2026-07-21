# /code-review — Structured, example-driven review

Perform a structured review for architecture, correctness, security, performance, and maintainability. Learn the intended style **from examples** before judging.

## Arguments (`$ARGUMENTS`)
- `paths`: files/dirs to review (defaults to the current branch diff vs `main`)
- `style_examples`: exemplar files to match design/style/conventions of. If omitted, first read the **nearest existing file** to whatever you're reviewing and infer its core design/style/coding principles.
- `severity_threshold`: `p0 | p1 | p2` — minimum severity to report (default `p2`)

## Process
1. **Learn style from examples** — read `style_examples` (or the nearest sibling file). Identify its core design principles, naming, error handling, and layering. Do not copy verbatim — extract the principles.
2. **Review `paths` against a checklist:**
   - **Correctness** — logic, edge cases, error paths, async/await misuse, race conditions.
   - **Security** — secrets in code, authz on every endpoint (`Depends(require_role(...))`), PHI/PII handling, injection, signature/verification correctness.
   - **Architecture** — SOLID, single responsibility, module boundaries, adapter/port cleanliness (external systems behind ABCs), file/size fit for AI-scalability.
   - **Performance** — N+1 queries, missing indexes vs. hot query paths (schema §B.3), unbounded loops, token/cost blowups.
   - **Maintainability** — naming matches domain vocabulary, tests present, docstrings/type hints, no dead code.
   - **SimForge invariants** — sandbox isolation (no Village writes), version pinning on CertSnapshots, gate auto-fail conditions, fingerprint checks.
3. **Produce issues** — each with: file:line, severity, the problem, why it matters (concrete failure scenario), and a suggested patch.
4. **Summarize by severity**, then output a **ready-to-paste PR comment**.
5. Optionally write per-file critiques to `<filename>.review.md`.

## Output
- Issues grouped P0 → P1 → P2, each with a suggested fix.
- A PR-comment-ready summary block.

## Example invocation
```
/code-review paths="apps/api/src/services/cert" \
  style_examples="apps/api/src/services/village/reader.py" severity_threshold=p1
```
