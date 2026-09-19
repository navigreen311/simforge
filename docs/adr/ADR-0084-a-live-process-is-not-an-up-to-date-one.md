# ADR-0084 — A live process is not an up-to-date one

**Status:** accepted · **Decided by:** Ivan Green, 19 September 2026 · **Built.**

---

## The ruling

**`/api/version` reports both the SHA the process was started with and the SHA the checkout is on
now, plus whether they differ, like The Office's. Report the launch environment alongside, since
`SCHEDULER_ENABLED` vanished on restart the same way.**

---

## What went wrong, and why every check passed

The API served commit `f13d7b1` for two days while the checkout sat at `0b2fb9e`, **sixteen commits
ahead.** A curriculum's `expected_answer` met a schema written before P1 and was discarded on
arrival.

Nothing caught it, and three things that look like they should have did not:

- the port answered;
- `/api/health` said `ok`;
- **`openapi.info.version` reported a SHA** — `f13d7b19e219…`, which is a real commit and was the
  wrong one.

**The SHA was never evidence.** `openapi.info.version` is `settings.app_version`, which is the
`APP_VERSION` environment variable with a default of `"1.0.0"`. Whoever launched the process on
17 September exported it by hand. It reported a SHA it was **told**, not one it **read** — and it
can be wrong in both directions: on the first restart of 19 September it reported `"1.0.0"` while
serving correct code.

**A label the launcher wrote on the box is not a fact about what is in it.**

## What was built

`GET /api/version`:

```json
{
  "started_commit":  "0b2fb9e…",
  "checkout_commit": "0b2fb9e…",
  "differs": false,
  "app_version": "0b2fb9e…",
  "launch_environment": {
    "modes": {"scheduler_enabled": false, "llm_provider": "auto", "exam_model_tag": "phi4:latest", …},
    "configured": {"database_url": true, "office_tenant_token": true, "clerk_secret_key": false, …}
  }
}
```

### Two numbers, because one cannot catch this

`started_commit` is resolved **once at import** and never again — the answer cannot change while
the process lives, and a value that moved under a caller would report the *checkout's* commit as the
*process's* own, which is precisely the confusion being ended. `checkout_commit` is read **per
request**, because that is the one that moves.

`SIMFORGE_GIT_COMMIT` first, then `APP_VERSION` when it looks like a SHA, then the working tree — an
image has no `.git` and stamps a variable; a development checkout has no stamp and can be asked.

### `differs: null` is the care in the whole change

**Never `false` when either side is unknown.** Returning `false` would tell a process that cannot
say what it is running that it is up to date — the one reassurance it must not be given. `null`
says *the check could not run*, which is not the same as *the check passed*.

### The launch environment, and why it is not `os.environ`

`SCHEDULER_ENABLED` was `true` before the restart and `false` after, because it lived only in the
old process's environment. Nothing said so; the batteries an operator believed were running were
not.

Reported from **`settings`**, not the environment, deliberately: what matters is the value the
process is *using*. A variable exported with a typo is present in `os.environ` and absent from
`settings`, and the second is the honest answer.

**Modes by value; credentials by presence.** Dumping the environment would put `DATABASE_URL`'s
password, the Clerk secret and The Office's tenant token into the response. `configured` answers
*was it exported* without answering *what is it*, which is the whole question an operator has. A
test asserts every entry there is a boolean and that no response body contains `postgresql://`,
`Bearer `, `sk-` or `password`.

## One divergence from The Office, named rather than decided

**The Office authenticates `/api/version`** and pins its unauthenticated surface to exactly two
routes, on the ground that telling an anonymous caller which build is running is a disclosure.

**This one is public**, because SimForge's health router is public by stated design and
`/api/health/config` already returns `app_version` and the entire seam configuration. Authenticating
this route alone would be a lock on an open door.

That is a real difference between the two systems' postures and it is worth a ruling; it was not
worth a private decision here.

## Read-only alongside

[Retiring the six exam runs](../retiring-the-six-runs-2026-09-19.md) — sized, nothing retired. The
short version: the content-hash binding already prevents a mechanical mis-match, so the risk is a
*reading*; a new state is the expensive answer and a column the cheap one; and **the database
already knows those verdicts are old, under `response_protocol_version`, and nothing asks it.**

Verified: 1,068 pass, 2 skip; ruff clean. The scheduler stays **off** pending Ivan's ruling.
