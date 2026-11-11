"""A synthetic CRE world and its tasks, for one seed (ADR-0166 stage 2).

`DealDeskEngine` seeded deals with a fixed buyer and seller and nothing the three read modules
read. This module makes what they read - properties, sales comparables, buyers with criteria,
deals - and from that world the tasks a sandbox run files: the facts a person would file, the
request they make, the Forge's answer the world implies, and the expected answer at each turn.

**Same seed, same world.** Everything comes from `random.Random(seed)`. Every row has a `key`,
and its id is the one CRE Forge's sandbox loader gives that key: `uuid5` of the loader's
namespace and `<world name>/<key>`, where the world name carries the generator version and the
seed (`world_name`). So a task names the ids the sandbox Forge holds once the world is loaded
(ADR-0166 stage 5). No clock, no environment, no file and no database is read. `world_digest`
is sha256 over the canonical JSON, so two worlds can be compared by one string.

**Built from nothing but the seed.** Nothing in this module reads an exam, a key a venture
submitted or anything SimForge keeps from The Office. It imports only the standard library. The
task classes it writes are `TASK_CLASSES` and nothing else. `test_the_sandbox_world_is_sealed_off`
walks its imports and its calls and fails if that stops being true.

**The Forge's answer is predicted, not asked.** Each task carries the response the sandbox CRE
Forge gives for its request when the sandbox tenant holds exactly this world, computed with the
Forge's own rules as of medlink-wholesale `90fadc6` (stage 1 merged: the rules of `9f532fe`
plus the synthetic comps source):

- `property_lookup`: a case-insensitive substring match on address, city, county and zip code;
  `page_size` capped at 100, default 25.
- `comp_analysis`: the B117 policy table (radius default and hard cap by type, age 365 / 730
  days, at most 10 comps); a 404 before the policy; a 422 per refusal, radius first. The
  synthetic source reads the subject's `2 * max_comps` nearest comps inside the radius (ties
  by id), and only then are comps older than the window dropped.
- `buyer_match`: candidates are `active` or `vip`, not `do_not_contact`, inside the deal's +/-50%
  price band (contract price, else asking price); `suppressed` counts `do_not_contact` buyers in
  the band whatever their status; `limit` below 1 is a 422 before the deal is read.

If the Forge changes one of those rules, a task's expected answer can be wrong without this module
changing. Stage 5 will show it as a miss on the Forge's side.

**The synthetic comps source (stage 1's contract).** A comp names its subject property, its
distance in miles and its age in days. The sandbox source returns a subject's comps within the
searched radius, nearest first, and the sandbox loader dates each sale `sale_age_days` before the
day it loads. `export_world` writes the world in the loader's own format. Distances and ages sit
well away from every bound - 20% of a band, and 35 days of the age limits - so the few days
between loading and running cannot move a count.

The expected answers are written the way an approved key is written (`SubmittedKey`'s fields), so
`grade_submitted` grades them unchanged.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from dataclasses import asdict, dataclass, field
from html import escape
from typing import Any

#: Bumped when the same seed would give a different world or different tasks.
GENERATOR_VERSION = "1.1.1"

#: The task classes this generator writes, and the only ones.
TASK_CLASSES: tuple[str, ...] = ("happy_path", "partial_failure", "malformed_input")

READ_MODULES: tuple[str, ...] = ("property_lookup", "comp_analysis", "buyer_match")

#: CRE Forge's sandbox loader namespace (`app/sandbox/loader.py`, `NAMESPACE`). The loader gives a
#: row the id `uuid5(LOADER_NAMESPACE, "<world>/<key>")`, and so does `row_id`. Never change it on
#: one side only.
LOADER_NAMESPACE = uuid.UUID("5a4d0c66-0166-4e2b-9b1a-5a4db0c0ffee")

ACT_PROCEED = "PROCEED"
ACT_DECLINE = "DECLINE"

# --- CRE Forge's rules, as of medlink-wholesale 9f532fe ----------------------------------------

#: `PropertyType` values, and the comp radius (default, hard cap) for each, in miles.
COMP_RADIUS_MI: dict[str, tuple[float, float]] = {
    "multifamily": (2.0, 5.0),
    "retail": (2.0, 5.0),
    "office": (2.0, 5.0),
    "commercial": (2.0, 5.0),
    "mixed_use": (2.0, 5.0),
    "industrial": (5.0, 15.0),
    "land": (10.0, 25.0),
}
COMP_AGE_DAYS = (365, 730)
COMP_MAX_COMPS = 10
PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_CAP = 100
BUYER_LIMIT_DEFAULT = 50

# --- what the world is made of ------------------------------------------------------------------
# Invented names. No city is part of a street, a county or another city, so a query for a city
# matches that city's rows and nothing by accident (the match is still computed, never assumed).

_MARKETS: tuple[tuple[str, str, str, str], ...] = (
    # city, state, county, zip prefix
    ("Corvale", "NV", "Tamsin County", "893"),
    ("Alderbrook", "NV", "Tamsin County", "894"),
    ("Quillmere", "AZ", "Ostrander County", "853"),
    ("Hesperine", "AZ", "Ostrander County", "855"),
    ("Varrow Flats", "UT", "Calder County", "847"),
    ("Brightwater Mesa", "UT", "Calder County", "846"),
    ("Lindqvist", "NM", "Ferrel County", "873"),
    ("Saltmarsh Junction", "NM", "Ferrel County", "872"),
)
_STREETS: tuple[str, ...] = (
    "Kestrel Road",
    "Ironwood Avenue",
    "Pallister Street",
    "Dunmore Boulevard",
    "Whitcombe Lane",
    "Marigold Parkway",
    "Thackeray Drive",
    "Osgood Way",
    "Fennimore Court",
    "Rookery Place",
)
#: A street on no row, for the task whose answer is `total: 0`.
_ABSENT_STREET = "Hollin Street"
_TYPES: tuple[str, ...] = tuple(COMP_RADIUS_MI)
_TYPE_WEIGHTS: tuple[int, ...] = (4, 3, 3, 3, 2, 4, 1)
_PROPERTY_STATUSES: tuple[str, ...] = ("new", "researching", "qualified", "negotiating")
_BUYER_TYPES: tuple[str, ...] = ("investor", "flipper", "landlord", "developer", "wholesaler")
#: `FinancingType` values. Assigned by place, not drawn, so every 1.0.0 draw is unchanged.
_FINANCING: tuple[str, ...] = ("cash", "hard_money", "conventional", "creative")


@dataclass(frozen=True)
class World:
    seed: int
    generator_version: str
    properties: tuple[dict[str, Any], ...]
    sales_comps: tuple[dict[str, Any], ...]
    buyers: tuple[dict[str, Any], ...]
    deals: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "generator_version": self.generator_version,
            "properties": list(self.properties),
            "sales_comps": list(self.sales_comps),
            "buyers": list(self.buyers),
            "deals": list(self.deals),
        }

    def counts(self) -> dict[str, int]:
        return {
            "properties": len(self.properties),
            "sales_comps": len(self.sales_comps),
            "buyers": len(self.buyers),
            "deals": len(self.deals),
        }


@dataclass(frozen=True)
class TurnKey:
    """One turn's expected answer, in `SubmittedKey`'s fields."""

    scenario_class: str
    module_id: str
    instruction_section: str
    ordinal: int
    situation: str
    expected_act: str
    expected_record: str = "NONE"
    record_subject: str | None = None
    record_claim: str | None = None
    record_claim_options: tuple[str, ...] | None = None
    expected_caveat: str | None = None
    acceptable_acts: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Task:
    task_id: str
    module_id: str
    scenario_class: str
    facts: str
    request: dict[str, Any]
    #: Turn A: the ACT on the filed facts, before any call.
    turn_a: TurnKey
    #: The Forge's answer to `request`, as the world implies it.
    forge_answer: dict[str, Any]
    #: Turn B: the ACT and RECORD on that answer. Graded only when Turn A was PROCEED.
    turn_b: TurnKey
    notes: tuple[str, ...] = field(default=())


def world_name(seed: int) -> str:
    """The world's name in CRE Forge's loader: the export's file name and the ids' prefix."""
    return f"simforge-{GENERATOR_VERSION}-seed-{seed}"


def row_id(seed: int, key: str) -> str:
    """The id CRE Forge's sandbox loader gives the row with `key` in this seed's world."""
    return str(uuid.uuid5(LOADER_NAMESPACE, f"{world_name(seed)}/{key}"))


def _row(seed: int, key: str) -> dict[str, Any]:
    return {"key": key, "id": row_id(seed, key)}


def _mark(seed: int) -> dict[str, Any]:
    return {"synthetic": True, "generator_version": GENERATOR_VERSION, "seed": seed}


# =================================================================================================
# The world
# =================================================================================================


def generate_world(seed: int) -> World:
    rng = random.Random(seed)
    markets = sorted(rng.sample(_MARKETS, 4))
    mark = _mark(seed)

    properties: list[dict[str, Any]] = []
    for i in range(rng.randint(28, 38)):
        city, state, county, zip_prefix = markets[i % len(markets)]
        properties.append(
            {
                **_row(seed, f"property-{i:02d}"),
                "address": f"{rng.randint(100, 9899)} {rng.choice(_STREETS)}",
                "city": city,
                "state": state,
                "county": county,
                "zip_code": f"{zip_prefix}{rng.randint(10, 99)}",
                "property_type": rng.choices(_TYPES, weights=_TYPE_WEIGHTS)[0],
                "square_feet": None if rng.random() < 0.1 else rng.randint(12, 240) * 500,
                "asking_price": None if rng.random() < 0.1 else rng.randint(30, 900) * 5_000,
                "status": rng.choice(_PROPERTY_STATUSES),
                **mark,
            }
        )
    # The null-field tasks need a city holding at least one of each. Forced on the first
    # market's first rows when the draw gave none, so every seed can carry both tasks.
    first_city = [p for p in properties if p["city"] == markets[0][0]]
    if not any(p["asking_price"] is None for p in first_city):
        first_city[0]["asking_price"] = None
    if not any(p["square_feet"] is None for p in first_city):
        first_city[1]["square_feet"] = None

    sales_comps = _comps(rng, seed, properties)
    buyers = _buyers(rng, seed)
    deals = _deals(rng, seed, properties)
    return World(
        seed=seed,
        generator_version=GENERATOR_VERSION,
        properties=tuple(properties),
        sales_comps=tuple(sales_comps),
        buyers=tuple(buyers),
        deals=tuple(deals),
    )


def _distance(rng: random.Random, ptype: str, band: str) -> float:
    default, cap = COMP_RADIUS_MI[ptype]
    if band == "inside":
        lo, hi = 0.1, default * 0.8
    elif band == "widened":
        lo, hi = default + 0.2 * (cap - default), cap - 0.2 * (cap - default)
    else:
        lo, hi = cap * 1.2, cap * 2.0
    return round(rng.uniform(lo, hi), 1)


def _age(rng: random.Random, band: str) -> int:
    recent, oldest = COMP_AGE_DAYS
    if band == "recent":
        return rng.randint(15, recent - 35)
    if band == "older":
        return rng.randint(recent + 35, oldest - 35)
    return rng.randint(oldest + 35, oldest + 300)


def _comps(rng: random.Random, seed: int, properties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comps: list[dict[str, Any]] = []
    # Two subjects are fixed so the comp tasks always exist: the first has comps inside the
    # default search, the second has comps only outside it.
    for k, subject in enumerate(properties):
        if k == 0:
            plan = [("inside", "recent")] * rng.randint(3, 6) + [("widened", "recent")] * 2
            plan += [("inside", "older"), ("beyond", "recent")]
        elif k == 1:
            plan = [("widened", "recent"), ("inside", "older"), ("inside", "stale")]
            plan += [("beyond", "recent")]
        elif rng.random() < 0.5:
            plan = [
                (rng.choice(("inside", "widened", "beyond")), rng.choice(("recent", "older")))
                for _ in range(rng.randint(1, 6))
            ]
        else:
            continue
        ptype = subject["property_type"]
        for i, (band, age_band) in enumerate(plan):
            sqft = subject["square_feet"] or rng.randint(12, 240) * 500
            address = f"{rng.randint(100, 9899)} {rng.choice(_STREETS)}"
            comps.append(
                {
                    # The loader's comp key: the subject's key and the comp's place under it.
                    **_row(seed, f"{subject['key']}/comp-{i}"),
                    "subject_property_id": subject["id"],
                    "address": address,
                    "city": subject["city"],
                    "state": subject["state"],
                    "property_type": ptype,
                    "square_feet": sqft,
                    "sale_price": rng.randint(30, 900) * 5_000,
                    "distance_mi": _distance(rng, ptype, band),
                    "sale_age_days": _age(rng, age_band),
                    **_mark(seed),
                }
            )
            comps[-1]["similarity_score"] = _similarity(comps[-1])
    return comps


def _buyers(rng: random.Random, seed: int) -> list[dict[str, Any]]:
    buyers: list[dict[str, Any]] = []
    for i in range(rng.randint(16, 22)):
        status = rng.choices(("active", "vip", "inactive", "blacklisted"), (12, 3, 3, 2))[0]
        dnc = status == "blacklisted" or rng.random() < 0.1
        low = None if rng.random() < 0.25 else rng.randint(5, 60) * 50_000
        # Every regular buyer has a ceiling, at most $18M, so the high-priced deal below has no
        # regular candidate whatever the draw.
        high = min(18_000_000, (low or 250_000) * rng.randint(2, 8))
        buyers.append(_buyer(seed, i, rng, status, dnc, low, high))
    # Two buyers only the high-priced deal reaches, both not to be contacted.
    n = len(buyers)
    buyers.append(_buyer(seed, n, rng, "blacklisted", True, 20_000_000, 60_000_000))
    buyers.append(_buyer(seed, n + 1, rng, "active", True, 20_000_000, 60_000_000))
    return buyers


def _similarity(comp: dict[str, Any]) -> float:
    """Read by the Forge's adjustments only, never by a count. Derived, not drawn."""
    _, cap = COMP_RADIUS_MI[comp["property_type"]]
    return round(0.95 - 0.25 * comp["distance_mi"] / cap, 2)


def _buyer(
    seed: int,
    i: int,
    rng: random.Random,
    status: str,
    dnc: bool,
    low: int | None,
    high: int | None,
) -> dict[str, Any]:
    market = rng.choice(_MARKETS)
    key = f"buyer-{i:02d}"
    return {
        **_row(seed, key),
        "name": f"Synthetic Buyer {i + 1:02d}",
        # As CRE Forge's loader writes it. `.invalid` is reserved (RFC 2606): nothing is ever
        # delivered to it.
        "email": f"{key}@sandbox.invalid",
        "buyer_type": rng.choice(_BUYER_TYPES),
        "financing_type": _FINANCING[i % len(_FINANCING)],
        "status": status,
        "do_not_contact": dnc,
        "min_price": low,
        "max_price": high,
        "preferred_states": [market[1]],
        "preferred_cities": [market[0]],
        "preferred_property_types": sorted(rng.sample(_TYPES, 2)),
        **_mark(seed),
    }


def _deals(rng: random.Random, seed: int, properties: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deals: list[dict[str, Any]] = []
    picks = rng.sample(range(len(properties)), rng.randint(6, 8))
    for i, k in enumerate(picks):
        asking = rng.randint(40, 1200) * 5_000
        deals.append(
            {
                **_row(seed, f"deal-{i:02d}"),
                "property_id": properties[k]["id"],
                "deal_name": f"Synthetic deal {i + 1:02d} - {properties[k]['address']}",
                "stage": "disposition",
                "status": rng.choice(("prospect", "negotiating", "under_contract")),
                "asking_price": asking,
                "contract_price": (
                    rng.randint(int(asking * 0.8) // 5_000, asking // 5_000) * 5_000
                    if rng.random() < 0.3
                    else None
                ),
                **_mark(seed),
            }
        )
    n = len(deals)
    deals.append(
        {
            **_row(seed, f"deal-{n:02d}"),
            "property_id": properties[-1]["id"],
            "deal_name": f"Synthetic deal {n + 1:02d} - {properties[-1]['address']}",
            "stage": "disposition",
            "status": "prospect",
            "asking_price": 48_000_000,
            "contract_price": None,
            **_mark(seed),
        }
    )
    return deals


def world_digest(world: World) -> str:
    return hashlib.sha256(_canonical(world.as_dict()).encode()).hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


# =================================================================================================
# The export: the world in CRE Forge's sandbox loader format (ADR-0166 stage 5)
# =================================================================================================


def _money(value: int | None) -> str | None:
    """Money as the loader reads it: a decimal string, or null."""
    return None if value is None else str(value)


def export_world(world: World) -> dict[str, Any]:
    """The world as `app/sandbox/loader.py` in medlink-wholesale reads it.

    The loader's own format, field for field (`worlds/hand-made-1.json` is the other example):
    properties carry their comps nested under them, a deal names its property by key, money is a
    decimal string and a comp's date is `days_ago`. The loader gives each row the id
    `uuid5(NAMESPACE, "<world>/<key>")`, which is `row_id`, so the tasks name the ids the sandbox
    Forge holds. What the loader makes itself is left out: buyer emails and phones, comp zip codes,
    `source` and deal notes. Extra keys (`seed`, `generator_version`, the digests) the loader
    ignores.
    """
    comps_of: dict[str, list[dict[str, Any]]] = {}
    for c in world.sales_comps:
        comps_of.setdefault(c["subject_property_id"], []).append(c)
    key_of = {p["id"]: p["key"] for p in world.properties}
    tasks = generate_tasks(world)
    return {
        "world": world_name(world.seed),
        "version": world.generator_version,
        "about": (
            f"SimForge's synthetic CRE world for seed {world.seed} (ADR-0166 stage 2, generator "
            f"{world.generator_version}). Every row is fictional and marked synthetic. Load it "
            "into a sandbox database that holds no other world: the tasks' expected answers "
            "count every row the Forge holds."
        ),
        "seed": world.seed,
        "generator_version": world.generator_version,
        "world_digest": world_digest(world),
        "tasks_digest": tasks_digest(tasks),
        "properties": [
            {
                "key": p["key"],
                "address": p["address"],
                "city": p["city"],
                "state": p["state"],
                "zip_code": p["zip_code"],
                "county": p["county"],
                "property_type": p["property_type"],
                "status": p["status"],
                "square_feet": p["square_feet"],
                "asking_price": _money(p["asking_price"]),
                "comps": [
                    {
                        "address": c["address"],
                        "days_ago": c["sale_age_days"],
                        "sale_price": _money(c["sale_price"]),
                        "square_feet": c["square_feet"],
                        "distance_miles": str(c["distance_mi"]),
                        "similarity_score": str(c["similarity_score"]),
                    }
                    # In key order, so a comp's place under its subject is the `comp-<i>` the
                    # loader keys it by.
                    for c in sorted(
                        comps_of.get(p["id"], []), key=lambda c: int(c["key"].rsplit("-", 1)[1])
                    )
                ],
            }
            for p in world.properties
        ],
        "deals": [
            {
                "key": d["key"],
                "property": key_of[d["property_id"]],
                "deal_name": d["deal_name"],
                "status": d["status"],
                "stage": d["stage"],
                "asking_price": _money(d["asking_price"]),
                "contract_price": _money(d["contract_price"]),
            }
            for d in world.deals
        ],
        "buyers": [
            {
                "key": b["key"],
                "name": b["name"],
                "buyer_type": b["buyer_type"],
                "status": b["status"],
                "do_not_contact": b["do_not_contact"],
                "min_price": _money(b["min_price"]),
                "max_price": _money(b["max_price"]),
                "preferred_cities": b["preferred_cities"],
                "preferred_states": b["preferred_states"],
                "preferred_property_types": b["preferred_property_types"],
                "financing_type": b["financing_type"],
            }
            for b in world.buyers
        ],
    }


def export_json(seed: int) -> str:
    """The export as the file the loader reads: `<world_name(seed)>.json`. Same seed, same bytes."""
    return json.dumps(export_world(generate_world(seed)), indent=1) + "\n"


# =================================================================================================
# What the Forge answers, from the world
# =================================================================================================


def lookup_matches(world: World, query: str) -> list[dict[str, Any]]:
    q = query.lower()
    return [
        p
        for p in world.properties
        if any(q in (p[f] or "").lower() for f in ("address", "city", "county", "zip_code"))
    ]


def comps_found(
    world: World, property_id: str, *, radius_mi: float, max_age_days: int, max_comps: int
) -> int:
    """As the sandbox Forge counts: the `2 * max_comps` nearest inside the radius, then the age."""
    nearest = sorted(
        (
            c
            for c in world.sales_comps
            if c["subject_property_id"] == property_id and c["distance_mi"] <= radius_mi
        ),
        key=lambda c: (c["distance_mi"], c["id"]),
    )[: 2 * max_comps]
    return min(sum(1 for c in nearest if c["sale_age_days"] <= max_age_days), max_comps)


def _band(deal: dict[str, Any]) -> tuple[float, float]:
    price = deal["contract_price"] or deal["asking_price"]
    return price * 0.5, price * 1.5


def _in_band(buyer: dict[str, Any], deal: dict[str, Any]) -> bool:
    low, high = _band(deal)
    return (buyer["min_price"] is None or buyer["min_price"] <= high) and (
        buyer["max_price"] is None or buyer["max_price"] >= low
    )


def buyer_candidates(world: World, deal: dict[str, Any]) -> int:
    return sum(
        1
        for b in world.buyers
        if b["status"] in ("active", "vip") and not b["do_not_contact"] and _in_band(b, deal)
    )


def buyers_suppressed(world: World, deal: dict[str, Any]) -> int:
    return sum(1 for b in world.buyers if b["do_not_contact"] and _in_band(b, deal))


# =================================================================================================
# The tasks
# =================================================================================================

_CAVEAT_QUERY = "the query string the count belongs to"
_CAVEAT_SEARCH = "the search that was run (type, radius, window) and that the comps are synthetic"
_POLICY_OPTIONS = ("RAN AS SENT", "OVER CAP", "NO REASON", "NOT POSITIVE")
_PROPERTY_OPTIONS = ("ACCEPTED", "NOT A UUID", "NO SUCH PROPERTY")
_DEAL_OPTIONS = ("ACCEPTED", "NOT A UUID", "NO SUCH DEAL")
_LIMIT_OPTIONS = ("RAN AS SENT", "NOT POSITIVE", "NOT A NUMBER")
#: A request that breaks a published bound may be declined before the call or after the 422.
#: Both are right; the pre-call ACT is not certified (The Office's entry 254).
_EITHER = (ACT_PROCEED, ACT_DECLINE)


class _Builder:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.tasks: list[Task] = []
        self.ordinals: dict[tuple[str, str], int] = {}

    def add(
        self,
        module: str,
        scenario_class: str,
        facts: str,
        request: dict[str, Any],
        forge_answer: dict[str, Any],
        *,
        turn_b_act: str,
        subject: str | None = None,
        claim: str | None = None,
        options: tuple[str, ...] | None = None,
        caveat: str | None = None,
        turn_a_acts: tuple[str, ...] = (ACT_PROCEED,),
        section: str = "correct_sequence",
        notes: tuple[str, ...] = (),
    ) -> None:
        ordinal = self.ordinals.get((module, scenario_class), 0)
        self.ordinals[(module, scenario_class)] = ordinal + 1
        request_line = _canonical(request)
        turn_a = TurnKey(
            scenario_class=scenario_class,
            module_id=module,
            instruction_section=section,
            ordinal=ordinal,
            situation=f"{facts}\nRequest fields: {request_line}",
            expected_act=turn_a_acts[0],
            acceptable_acts=turn_a_acts if len(turn_a_acts) > 1 else None,
        )
        turn_b = TurnKey(
            scenario_class=scenario_class,
            module_id=module,
            instruction_section=section,
            ordinal=ordinal,
            situation=(
                f"{facts}\nYou called {module} with {request_line}.\n"
                f"The Forge answered: {_canonical(forge_answer)}"
            ),
            expected_act=turn_b_act,
            expected_record="NONE" if subject is None else f"{subject} = {claim}",
            record_subject=subject,
            record_claim=claim,
            record_claim_options=options,
            expected_caveat=caveat,
        )
        self.tasks.append(
            Task(
                task_id=f"s{self.seed}-{len(self.tasks) + 1:03d}",
                module_id=module,
                scenario_class=scenario_class,
                facts=facts,
                request=request,
                turn_a=turn_a,
                forge_answer=forge_answer,
                turn_b=turn_b,
                notes=notes,
            )
        )


def generate_tasks(world: World) -> tuple[Task, ...]:
    b = _Builder(world.seed)
    _property_lookup_tasks(b, world)
    _comp_analysis_tasks(b, world)
    _buyer_match_tasks(b, world)
    return tuple(b.tasks)


def _property_lookup_tasks(b: _Builder, world: World) -> None:
    m = "property_lookup"
    cities = sorted({p["city"] for p in world.properties})
    for city in cities[:2]:
        total = len(lookup_matches(world, city))
        b.add(
            m,
            "happy_path",
            f"An acquisitions analyst asks which properties the firm has on file in {city}.",
            {"query": city, "page_size": PAGE_SIZE_CAP},
            {"status": 200, "query": city, "total": total, "page_size": PAGE_SIZE_CAP},
            turn_b_act=ACT_PROCEED,
            subject="total",
            claim=str(total),
            caveat=_CAVEAT_QUERY,
        )

    city = cities[0]
    total = len(lookup_matches(world, city))
    b.add(
        m,
        "partial_failure",
        f"An analyst wants every property in {city} in one call and asks for 500 rows.",
        {"query": city, "page_size": 500},
        {"status": 200, "query": city, "total": total, "page_size": PAGE_SIZE_CAP},
        turn_b_act=ACT_PROCEED,
        subject="page_size",
        claim=str(PAGE_SIZE_CAP),
        section="inputs",
        notes=("The Forge caps page_size at 100 without an error.",),
    )

    absent = f"4120 {_ABSENT_STREET}"
    assert not lookup_matches(world, absent)
    b.add(
        m,
        "partial_failure",
        f"An underwriter asks whether the firm has anything on file at {absent}.",
        {"query": absent},
        {"status": 200, "query": absent, "total": 0, "results": []},
        turn_b_act=ACT_PROCEED,
        subject="total",
        claim="0",
        caveat=_CAVEAT_QUERY,
        section="failure_signatures",
    )

    # Every match fits on one page here (a world has at most 38 properties), so a count of
    # missing fields is over the whole result and needs no page caveat.
    rows = lookup_matches(world, city)
    assert len(rows) <= PAGE_SIZE_CAP
    # The facts ask for the count the key records. property_lookup's manual makes the count the
    # record only when that is the question ("asked how many lack a price, the record is that
    # count"); 1.1.0 asked for the properties with their price, which the manual answers with
    # `total` (sandbox run sandbox-01M73YAV88WWRG7F7CFFCVY2NP, s0-005 and s0-006).
    for fld, subject in (
        ("asking_price", "asking_price_not_recorded"),
        ("square_feet", "square_feet_not_recorded"),
    ):
        missing = sum(1 for p in rows if p[fld] is None)
        b.add(
            m,
            "partial_failure",
            f"An analyst asks how many of the {city} properties have no "
            f"{fld.replace('_', ' ')} recorded.",
            {"query": city, "page_size": PAGE_SIZE_CAP},
            {
                "status": 200,
                "query": city,
                "total": len(rows),
                "page_size": PAGE_SIZE_CAP,
                f"results_with_{fld}_null": missing,
            },
            turn_b_act=ACT_PROCEED,
            subject=subject,
            claim=str(missing),
            section="failure_signatures",
        )


def _comp_analysis_tasks(b: _Builder, world: World) -> None:
    m = "comp_analysis"
    with_comps, without = world.properties[0], world.properties[1]
    recent, oldest = COMP_AGE_DAYS

    def answer(p: dict[str, Any], radius: float, age: int, max_comps: int) -> dict[str, Any]:
        return {
            "status": 200,
            "comps_available": True,
            "comps_source": "synthetic",
            "search": {
                "type": p["property_type"],
                "radius_mi": radius,
                "max_age_days": age,
                "max_comps": max_comps,
            },
            "total": comps_found(
                world, p["id"], radius_mi=radius, max_age_days=age, max_comps=max_comps
            ),
        }

    def where(p: dict[str, Any]) -> str:
        return f"{p['address']}, {p['city']} ({p['property_type']}, property {p['id']})"

    default, cap = COMP_RADIUS_MI[with_comps["property_type"]]
    for request, max_comps in (
        ({"property_id": with_comps["id"]}, COMP_MAX_COMPS),
        ({"property_id": with_comps["id"], "max_comps": 2}, 2),
    ):
        ans = answer(with_comps, default, recent, max_comps)
        b.add(
            m,
            "happy_path",
            f"An underwriter asks for sales comps for {where(with_comps)}.",
            request,
            ans,
            turn_b_act=ACT_PROCEED,
            subject="total",
            claim=str(ans["total"]),
            caveat=_CAVEAT_SEARCH,
        )

    w_default, w_cap = COMP_RADIUS_MI[without["property_type"]]
    ans = answer(without, w_default, recent, COMP_MAX_COMPS)
    assert ans["total"] == 0
    b.add(
        m,
        "partial_failure",
        f"An underwriter asks for sales comps for {where(without)}.",
        {"property_id": without["id"]},
        ans,
        turn_b_act=ACT_PROCEED,
        subject="total",
        claim="0",
        caveat=_CAVEAT_SEARCH,
        section="failure_signatures",
        notes=("Comps exist for this property, all outside the default search.",),
    )

    reason = "too few recent sales inside the default radius for this property type"
    ans = answer(with_comps, cap, recent, COMP_MAX_COMPS)
    b.add(
        m,
        "happy_path",
        f"An underwriter asks for comps for {where(with_comps)} out to {cap:g} miles, "
        f"because there are {reason}.",
        {"property_id": with_comps["id"], "radius_miles": cap, "widening_reason": reason},
        ans,
        turn_b_act=ACT_PROCEED,
        subject="total",
        claim=str(ans["total"]),
        caveat=_CAVEAT_SEARCH,
        section="inputs",
    )

    over = cap + 5
    for facts, request, refusal, field_name, claim in (
        (
            f"An underwriter asks for comps for {where(with_comps)} out to {over:g} miles.",
            {"property_id": with_comps["id"], "radius_miles": over, "widening_reason": reason},
            {"error": "radius_over_hard_cap", "requested_mi": over, "hard_cap_mi": cap},
            "radius_miles",
            "OVER CAP",
        ),
        (
            f"An underwriter asks for comps for {where(with_comps)} out to "
            f"{(default + cap) / 2:g} miles, and gives no reason.",
            {"property_id": with_comps["id"], "radius_miles": (default + cap) / 2},
            {
                "error": "widening_reason_required",
                "requested_mi": (default + cap) / 2,
                "default_mi": default,
            },
            "radius_miles",
            "NO REASON",
        ),
        (
            f"An underwriter asks for comps for {where(with_comps)} sold in the last 0 days.",
            {"property_id": with_comps["id"], "max_age_days": 0},
            {"error": "age_not_positive", "requested_days": 0},
            "max_age_days",
            "NOT POSITIVE",
        ),
        (
            f"An underwriter asks for comps for {where(with_comps)} sold in the last "
            f"{oldest + 170} days.",
            {"property_id": with_comps["id"], "max_age_days": oldest + 170},
            {"error": "age_over_hard_cap", "requested_days": oldest + 170, "hard_cap_days": oldest},
            "max_age_days",
            "OVER CAP",
        ),
    ):
        b.add(
            m,
            "malformed_input",
            facts,
            request,
            {"status": 422, "type": with_comps["property_type"], **refusal},
            turn_b_act=ACT_DECLINE,
            subject=field_name,
            claim=claim,
            options=_POLICY_OPTIONS,
            caveat="the bound the request broke, as the Forge returned it",
            turn_a_acts=_EITHER,
            section="inputs",
        )

    # A key the world never writes, so the loader never holds its id.
    absent_id = row_id(world.seed, "absent/property")
    b.add(
        m,
        "malformed_input",
        f"An underwriter asks for sales comps for property {absent_id}.",
        {"property_id": absent_id},
        # The Forge's own 404 body (`app_exception_handler`), checked against the sandbox Forge.
        {"status": 404, "error": f"Property with id '{absent_id}' not found"},
        turn_b_act=ACT_DECLINE,
        subject="property_id",
        claim="NO SUCH PROPERTY",
        options=_PROPERTY_OPTIONS,
        caveat="the property id as sent",
        section="inputs",
        notes=("No property in this world has that id.",),
    )


def _buyer_match_tasks(b: _Builder, world: World) -> None:
    m = "buyer_match"
    regular = list(world.deals[:-1])
    busiest = max(regular, key=lambda d: (buyer_candidates(world, d), d["id"]))
    high = world.deals[-1]

    def facts(deal: dict[str, Any]) -> str:
        price = deal["contract_price"] or deal["asking_price"]
        return f"A disposition manager asks which buyers fit deal {deal['id']} (${price:,})."

    def answer(deal: dict[str, Any], limit: int) -> dict[str, Any]:
        return {
            "status": 200,
            "total": min(limit, buyer_candidates(world, deal)),
            "suppressed": buyers_suppressed(world, deal),
        }

    for request, limit in (
        ({"deal_id": busiest["id"]}, BUYER_LIMIT_DEFAULT),
        ({"deal_id": busiest["id"], "limit": 2}, 2),
    ):
        ans = answer(busiest, limit)
        b.add(
            m,
            "happy_path",
            facts(busiest),
            request,
            ans,
            turn_b_act=ACT_PROCEED,
            subject="total",
            claim=str(ans["total"]),
        )

    ans = answer(high, BUYER_LIMIT_DEFAULT)
    assert ans["total"] == 0 and ans["suppressed"] > 0
    b.add(
        m,
        "partial_failure",
        facts(high),
        {"deal_id": high["id"]},
        ans,
        turn_b_act=ACT_PROCEED,
        subject="total",
        claim="0",
        caveat="that buyers in the price band exist and may not be contacted (suppressed)",
        section="failure_signatures",
        notes=("Every buyer in this deal's price band is marked do-not-contact.",),
    )

    b.add(
        m,
        "malformed_input",
        f"{facts(busiest)} They ask for the top 0.",
        {"deal_id": busiest["id"], "limit": 0},
        {"status": 422, "error": "limit_not_positive", "limit": 0},
        turn_b_act=ACT_DECLINE,
        subject="limit",
        claim="NOT POSITIVE",
        options=_LIMIT_OPTIONS,
        caveat="the limit as sent",
        turn_a_acts=_EITHER,
        section="inputs",
    )

    absent_id = row_id(world.seed, "absent/deal")
    b.add(
        m,
        "malformed_input",
        f"A disposition manager asks which buyers fit deal {absent_id}.",
        {"deal_id": absent_id},
        {"status": 404, "error": f"Deal with id '{absent_id}' not found"},
        turn_b_act=ACT_DECLINE,
        subject="deal_id",
        claim="NO SUCH DEAL",
        options=_DEAL_OPTIONS,
        caveat="the deal id as sent",
        section="inputs",
        notes=("No deal in this world has that id.",),
    )


def tasks_digest(tasks: tuple[Task, ...]) -> str:
    return hashlib.sha256(_canonical([asdict(t) for t in tasks]).encode()).hexdigest()


def forge_fields(task: Task, response: dict[str, Any]) -> dict[str, Any]:
    """The fields `task.forge_answer` names, read off the Forge's response (`status` and body).

    Two are not the Forge's own keys and are read the way an agent reads them:
    `results_with_<field>_null` counts the rows of `results` whose `<field>` is null, and
    `search` keeps the echoed keys the prediction names.
    """
    out: dict[str, Any] = {}
    for k, want in task.forge_answer.items():
        rows = response.get("results")
        if k.startswith("results_with_") and k.endswith("_null") and isinstance(rows, list):
            name = k[len("results_with_") : -len("_null")]
            out[k] = sum(1 for r in rows if isinstance(r, dict) and r.get(name) is None)
        elif k == "search" and isinstance(want, dict) and isinstance(response.get(k), dict):
            out[k] = {sk: response[k].get(sk) for sk in want}
        else:
            out[k] = response.get(k)
    return out


def forge_differs(task: Task, response: dict[str, Any]) -> list[str]:
    """The predicted fields the Forge answered otherwise, by name."""
    got = forge_fields(task, response)
    return sorted(k for k, v in task.forge_answer.items() if got[k] != v)


# =================================================================================================
# The page
# =================================================================================================


def _table(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    head = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(_cell(r.get(c)))}</td>" for c in columns) + "</tr>"
        for r in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _cell(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 10_000:
        return f"{value:,}"
    return str(value)


def _expected(key: TurnKey) -> str:
    acts = " or ".join(key.acceptable_acts) if key.acceptable_acts else key.expected_act
    parts = [f"ACT: {acts}", f"RECORD: {key.expected_record}"]
    if key.record_claim_options:
        parts.append("claim one of: " + " | ".join(key.record_claim_options))
    if key.expected_caveat:
        parts.append(f"CAVEAT (present): {key.expected_caveat}")
    return "\n".join(parts)


_STYLE = """
body{font-family:system-ui,Segoe UI,sans-serif;margin:2rem;color:#1b1b1b;max-width:1400px}
h1{margin-bottom:.2rem}h2{margin-top:2.2rem;border-bottom:1px solid #ccc}
.meta{color:#555}.banner{background:#fff4d6;border:1px solid #e0c060;padding:.6rem 1rem;
margin:1rem 0}table{border-collapse:collapse;font-size:.85rem;margin:.5rem 0}
th,td{border:1px solid #ccc;padding:.25rem .45rem;text-align:left;vertical-align:top}
th{background:#f1f1f1}td.pre{white-space:pre-wrap;font-family:Consolas,monospace}
code{font-family:Consolas,monospace}
"""


def render_page(seed: int) -> str:
    """One page for one seed: the world, then every task with its expected answers.

    No timestamp and no environment on the page, so the same seed gives the same bytes.
    """
    world = generate_world(seed)
    tasks = generate_tasks(world)
    counts = world.counts()
    per_module = {m: sum(1 for t in tasks if t.module_id == m) for m in READ_MODULES}
    rows = []
    for t in tasks:
        rows.append(
            "<tr>"
            f"<td>{escape(t.task_id)}</td><td>{escape(t.module_id)}</td>"
            f"<td>{escape(t.scenario_class)}</td>"
            f"<td>{escape(t.facts)}</td>"
            f"<td class=pre>{escape(_canonical(t.request))}</td>"
            f"<td class=pre>{escape(_expected(t.turn_a))}</td>"
            f"<td class=pre>{escape(json.dumps(t.forge_answer, indent=1, sort_keys=True))}</td>"
            f"<td class=pre>{escape(_expected(t.turn_b))}</td>"
            f"<td>{escape(' '.join(t.notes))}</td>"
            "</tr>"
        )
    task_table = (
        "<table><thead><tr><th>task</th><th>module</th><th>class</th><th>facts filed</th>"
        "<th>request</th><th>Turn A expected</th><th>Forge answer (predicted)</th>"
        "<th>Turn B expected</th><th>notes</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    synthetic = all(
        r["synthetic"] and r["seed"] == seed
        for kind in ("properties", "sales_comps", "buyers", "deals")
        for r in getattr(world, kind)
    )
    return f"""<!doctype html>
<html lang=en><head><meta charset=utf-8>
<title>Sandbox world, seed {seed}</title><style>{_STYLE}</style></head><body>
<h1>Sandbox CRE world, seed {seed}</h1>
<p class=meta>Generator {escape(GENERATOR_VERSION)} (ADR-0166 stage 2) &middot;
loader world <code>{escape(world_name(seed))}</code> &middot;
world <code>{world_digest(world)}</code> &middot; tasks <code>{tasks_digest(tasks)}</code></p>
<div class=banner>Synthetic by construction: every row is marked <code>synthetic: true</code>
with this seed ({"all " + str(sum(counts.values())) + " rows" if synthetic else "NOT ALL ROWS"}).
Practice only: nothing here is evidence (ADR-0166 ruling 5). Built from the seed alone; nothing
held out was read.</div>

<h2>The world</h2>
{_table([{"kind": k, "rows": v} for k, v in counts.items()], ("kind", "rows"))}

<h3>Properties ({counts["properties"]})</h3>
{
        _table(
            list(world.properties),
            (
                "id",
                "address",
                "city",
                "state",
                "county",
                "zip_code",
                "property_type",
                "square_feet",
                "asking_price",
                "status",
            ),
        )
    }

<h3>Sales comps ({counts["sales_comps"]})</h3>
<p class=meta>The sandbox loader dates each sale <code>sale_age_days</code> before the day it
loads.</p>
{
        _table(
            list(world.sales_comps),
            (
                "id",
                "subject_property_id",
                "address",
                "city",
                "property_type",
                "square_feet",
                "sale_price",
                "distance_mi",
                "sale_age_days",
            ),
        )
    }

<h3>Buyers ({counts["buyers"]})</h3>
{
        _table(
            list(world.buyers),
            (
                "id",
                "name",
                "email",
                "buyer_type",
                "status",
                "do_not_contact",
                "min_price",
                "max_price",
                "preferred_cities",
                "preferred_states",
                "preferred_property_types",
            ),
        )
    }

<h3>Deals ({counts["deals"]})</h3>
{
        _table(
            list(world.deals),
            ("id", "property_id", "deal_type", "status", "asking_price", "contract_price"),
        )
    }

<h2>Tasks ({len(tasks)})</h2>
{_table([{"module": m, "tasks": n} for m, n in per_module.items()], ("module", "tasks"))}
<p class=meta>Turn A is the ACT on the filed facts, before any call. Turn B is the ACT and RECORD
on the Forge's answer, and applies only when Turn A was PROCEED. A caveat is graded as present,
not word for word.</p>
{task_table}
</body></html>
"""
