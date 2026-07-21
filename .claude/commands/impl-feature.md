# /impl-feature — Plan & implement a complete feature end-to-end

Plan and implement a complete feature (design → code → tests → docs → demo) in its own branch, following the SimForge Recipe in `CLAUDE.md` §3.

## Arguments
Parse `$ARGUMENTS` as a small spec. Expected keys (ask 3–5 clarifying questions only for what's missing and materially affects correctness):
- `feature_name`: <kebab-case short name> — becomes the branch `ai-feature/<feature_name>`
- `scope`: `ui | api | fullstack | agent | infra`
- `acceptance_criteria`: bullet list or Gherkin
- `tech_constraints`: (optional) stack limits / integrations
- `priority`: `p0 | p1 | p2`
- `perf_targets`: (optional) performance goals
- `security_notes`: (optional) security / compliance notes

## Process
1. **Understand & Plan** — summarize the inputs; write a short mini-PRD (problem, users, success metrics, constraints, risks); outline the architecture (components, data model, APIs; Mermaid allowed); define the acceptance tests. Save to `docs/${feature_name}.md`. For complex features, `think hard` first.
2. **Branch & optional worktree** — `git checkout -b ai-feature/${feature_name}`. If the work is naturally parallel with other in-flight features, create a git worktree and say which commands you ran.
3. **Implement** — modify all necessary layers per `scope`. Keep cohesive, well-named modules and clear boundaries. Atomic Conventional Commits (`feat:`, `fix:`, …). Match the style of the nearest existing files.
4. **Tests** — create/extend unit + integration tests aligned to the acceptance criteria. Run them; they must pass. Backend: `pytest`. Frontend: `pnpm --filter web test` (vitest) / Playwright for E2E.
5. **Verify** — build/run, do local smoke tests, write a short demo script (commands + URL).
6. **Docs** — update `README.md`, finalize `docs/${feature_name}.md` (overview, architecture, endpoints, env vars), add a `CHANGELOG.md` entry (added/changed/removed).
7. **Deliver** — summary of changes, how to run, test results, known tradeoffs.

## Output Requirements
- Branch `ai-feature/${feature_name}` containing code + tests + docs.
- A closing summary block:
  ```
  IMPLEMENTED: <what>
  TESTED: <commands + results>
  HOW TO RUN: <commands + URL>
  TRADEOFFS / FOLLOW-UPS: <bullets>
  ```
- A **Fact-Check List** for any high-risk assumptions (versions, limits, security, cost).
- If multi-step, an idempotent automation artifact (script / pnpm script / make target).

## Error Handling
- On failure, show the logs, propose a fix, and retry.
- For missing info, make clearly labeled `ASSUMPTION:`s, proceed, and explain how to change them.

## Example invocation
```
/impl-feature feature_name=readiness-matrix scope=fullstack priority=p1 \
  acceptance_criteria="- Agent×Forge-cap grid renders with status dots + tier pills
                       - Filter by department and autonomy level
                       - Clicking a cell opens cert detail" \
  perf_targets="matrix renders < 500ms for 106 agents"
```
