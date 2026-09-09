# ADR-0050 — No credential fetches the held-out set

**Status:** accepted · **Decided by:** Ivan, 9 September 2026 · **Built by:** P-05b
**Supersedes nothing. Constrains:** ADR-0048 (the never-do trap), and the pipeline P-05 built.

---

## The question that was asked

P-05 built the held-out authoring pipeline — a declared never-do entry becomes a
`never_do_violation` probe, a claim prohibition in the same list becomes a `silent_failure` one, and
both are graded. It then escalated the seam it could not close from inside its own file list:

> The operation battery is not in this repository. For a held-out probe to reach an agent, a battery
> needs (a) a way to fetch the held-out set for a run and (b) a way to return what it observed.

and named the governance question rather than answering it alone:

> **Who may fetch the held-out set?** A `forge_owner` credential is what submits the curriculum. If
> the same credential can fetch the probes, ADR-0048's whole refusal is undone one endpoint over.

## The decision

**No credential fetches the held-out set. Not `forge_owner`, not the founder, not `admin`.**

There is no route, at any role, that returns held-out scenario content. The probe reaches the agent
under test at run time, inside a battery. Nobody fetches the set.

An inspection surface may exist and it returns **counts, ids and hashes — never content.**

## Why the alternative was refused, which is the part that must not be lost

An ADR that records a decision and not the refused alternative is the one reversed by the next
person who finds a fetch convenient. So, in Ivan's words:

> **An endpoint returning the corpus makes isolation a function of who holds a token**, and
> `ROLE_RANK` already means a strong enough role gets everything — ADR-0048's refusal undone one
> endpoint over.

> **"Eleven scenarios exist for this module" is inspectable; "here they are" is the exam.**

The first sentence is the whole argument. ADR-0048 refused a submitted `never_do_violation` scenario
because *"an agent graded against refusal cases its own authoring system wrote is measured on
memorisation, not competence."* A fetch endpoint would not contradict that rule; it would route
around it. The submitter would not author the probes — it would read them, which is worse, because
it looks compliant.

**A note on `ROLE_RANK`, read out of the code rather than the name (this project has been wrong
twice by reasoning from a name).** There is no `ROLE_RANK` constant in simforge. The mechanism Ivan
named is `Principal.has_role` in `src/auth/dev.py`:

```python
def has_role(self, role: str) -> bool:
    return role in self.roles or "admin" in self.roles
```

Any check answers True once `admin` is present. **So a role-gated fetch endpoint would have been
gated by nothing at all**, and the ruling is not merely prudent — it is the only correct reading of
the auth model this service actually has.

## What follows from it that the ruling does not state

**The operation battery has to run inside SimForge.** An external runner cannot put a probe it
cannot obtain, and the only way to obtain one would be the refused fetch. This is a consequence, not
a preference, and it has three visible effects:

1. Delivery is a function call — `held_out_scoring.run_held_out_battery` — not an endpoint.
2. **Nothing was added to `schemas/operation_payloads.py` on the inbound side.** P-05b was given
   permission to add an `ObservedBehaviour` field to `AgentRunOutcome` and declined it: a runner
   that could report an observation of a probe would have had to be handed the probe first, so the
   field would only ever be filled by a caller that had defeated this ADR.
3. There is no wire format for a probe, and `Probe` is deliberately not serialisable — no
   `model_dump`, no pydantic model. A probe that can be serialised is one route away from being
   returned by one.

## Three projections, each strictly narrower

| audience | sees | why not more |
|---|---|---|
| **submitter** | class, module, section (`for_submitter`) | three facts it already sent; a projection that adds no information is the only honest one |
| **operator** | counts and a digest (`inventory`) | *"eleven scenarios exist"* is the operator's question; the corpus is not |
| **agent under test** | the prompt (`Probe`) | no key, and **no scenario class** — an agent told "this is the never-do test" is examined on recognising a format, not on holding the line |

The third is the one most easily got wrong, and the missing field is `scenario_class`. The probes
are constructed to read like ordinary requests from a colleague with a good reason; one label would
undo that.

## The inspection surface, and where it stops short of what was permitted

Built: `GET /api/operation/held-out/{forge}/{module}` — obligations declared, scenarios authored,
counts by class, and a one-way digest of the set. The digest makes *"the same twelve scenarios as
last week"* checkable without anybody reading one, which is the audit property that would otherwise
have been the argument for returning them.

**Not built, though the ruling allows ids: per-scenario obligation ids.** An id would tell a
submitter which of *its own* never-do entries drew a `silent_failure` probe — i.e. which of its
sentences the parser read as claim prohibitions. That answers no operator question and is a fact
about the exam. The narrower surface is the one that survives somebody later deciding a little more
would be convenient.

## The refusal is a route, not an absence

`GET /api/operation/held-out/{forge}/{module}/scenarios` exists and **always answers 403**, with the
error code `held_out_content_is_never_returned`, the reasoning, a pointer to the inventory, and this
ADR number.

**A 404 would have been the wrong answer.** It reads as *"not built yet"* and invites exactly the
construction this ADR forbids; a 403 naming the ADR is the decision, left where somebody looking for
the corpus will find it instead of the corpus. The route's oddness is the record.

The refusal reads no role. `require_role("viewer")` sits on it only so the route is reachable enough
to *be* refused — a 401 for an anonymous caller would prove nothing about a credentialled one.

## Why this ADR is the one place the engine can prove something about itself

`GATE_9_5_FLAG` says, and continues to say:

> the engine cannot self-prove that isolation (same dependency as Gate 9.5)

That is true of the authoring side: no test here can show that whoever reads the instruction set to
author the held-out set is isolated from whoever could leak it. **But whether this service hands the
corpus to a caller is a question about this service**, and it is answerable — by demonstrating the
refusal, with a credential, against a running app.

`tests/integration/test_held_out_refusal.py` does exactly that, and it hands the route the most
privileged principal the system can construct: all eight roles, `admin` and `founder` among them. A
test that refused a `viewer` would have proved only that the weak are weak. This one proves that
strength does not help, which is the property the ruling asks for and the one a role check could
never have delivered.

## Consequences

- A future author who needs a probe across a process boundary writes a **new ADR**, not a serialiser.
- The name-level import guard (`ROUTER_MAY_IMPORT` in `tests/unit/test_held_out_authoring.py`) is
  what keeps a request handler structurally unable to hold a scenario. It replaced a module-level
  guard that this ADR made obsolete; the replacement is recorded in that file rather than silently
  swapped, because a test whose meaning changed quietly is worse than one that failed.
- **Still open, and not decided here:** what runs the in-process battery. This ADR settles that it
  must be in-process and settles nothing about what puts the questions to the agent.
