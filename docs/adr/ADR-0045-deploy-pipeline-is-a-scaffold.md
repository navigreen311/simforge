# ADR-0045 — The deploy pipeline is a scaffold, and it has been reporting success

**Status:** Accepted (the finding). The remedy is chosen; the deployment itself is not built here.
**Date:** 2026-09-04

## The finding

`.github/workflows/deploy-staging.yml` runs on every push to `main`. Its only step is:

```yaml
- run: echo "staging deploy pipeline (scaffold) — see docs/deploy.md"
```

Everything else in the job is a `# WEEK 9:` comment describing what it would do. It has
been passing green on every push to `main` for months, in ~7–10 seconds, while deploying
nothing.

`deploy-prod.yml` is the same shape behind `workflow_dispatch`.

## Why this is worse than having no pipeline

A repository with no deploy workflow says, accurately, that nothing deploys. This one says
the opposite. The Actions tab shows `deploy-staging ✓` beside `ci ✓` on every commit, and
those two ticks are indistinguishable — one ran 683 tests, the other ran `echo`.

**It is green because it does nothing.** That is the dead-control shape: a check whose
success carries no information, sitting where a reader reasonably expects information. The
cost is not the missing deployment, which everyone could have discovered; it is that the
green tick actively argues against looking.

Three concrete ways this misleads:

- **A reader believes staging exists.** It does not. There is no staging environment, no
  URL, no running instance of this API anywhere.
- **A reader believes a deploy could fail.** It cannot. `echo` does not fail, so the
  workflow has never had an opportunity to report a problem and never will.
- **The `environment: staging` key implies a configured GitHub environment with secrets and
  protection rules.** Nothing in the job reads a secret.

## What is actually true about deployability

Worth separating from the finding, because the picture is not uniformly bad:

| | |
|---|---|
| `apps/api/Dockerfile` | **Real.** 39 lines, multi-stage, non-root (uid 10001), healthchecked. ADR-0030. |
| Built in CI | No. Nothing builds it. |
| `docker-compose.yml` | postgres, redis, ollama. **No api service.** |
| `infra/k8s/` | Empty directory. |
| `infra/terraform/` | `ecs.tf`, `rds.tf`, `redis.tf`, `s3.tf`, `iam.tf` — never applied. |
| Deployed anywhere, ever | **No.** |

So the image is buildable and the app is runnable. What is absent is any pipeline that does
either, and any environment to do it to.

## Decision

**Make the workflows tell the truth, now, without building the deployment.**

The remedy is not to build a staging deploy in order to make a green tick honest — that is
the tail wagging the dog, and it is a large unscoped piece of work. It is to stop the
workflow claiming an outcome it does not produce. Either:

1. **Delete both workflows.** No workflow is an honest report of no deployment. The
   `# WEEK 9:` comments describing the intended pipeline move to `docs/deploy.md`, where
   they are a plan rather than a job that passes.
2. **Or make them fail.** A scaffold that exits non-zero with "not implemented" is honest,
   visible, and cannot be mistaken for a working pipeline — at the cost of a permanently
   red tick that people learn to ignore, which is its own dead control.

**Option 1 is preferred.** A red check nobody can fix trains readers to ignore red checks,
and that habit is more expensive than the missing workflow. A plan in `docs/deploy.md` with
no workflow beside it is unambiguous.

Not executed in this ADR: deleting a workflow is a change to what runs on `main`, and it
should be its own reviewable commit rather than a side effect of a Forge-adapter branch.

## What this does not decide

**Whether SimForge needs to be CI-reachable.** That is a separate question, and a live one:
The Office's V32 resolves a Pack's modules against `GET {base_url}/_modules`, and its Smoke
job runs on a GitHub runner that can reach neither a dev checkout nor an undeployed Forge.
CapitalForge has the same problem and it is recorded on that side
(`theoffice/docs/decisions.md`, entries 1 and 3). A real staging deployment would retire it
for SimForge. Nothing here commits to that.

**Whether the terraform is right.** It has never been applied, so it has never been
evaluated. Unapplied terraform is a proposal.

## How this was found

By asking what `example.invalid` was a placeholder *for*, while scoping The Office bridge —
not by the pipeline failing, because it cannot. Worth noting: the question that surfaced it
was about a different system entirely. Nothing inside this repository was ever going to
report it.
