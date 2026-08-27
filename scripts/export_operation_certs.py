"""Export the Operation Certification board as a self-contained static HTML file.

The Next.js dev server is unstable on some hosts, so this renders the same /dashboard/operation-certs
view to a single openable file (docs/operation-certs.html) with live data baked in — no server, no
external assets. It pulls from the same composed read-views the live page uses, so the export can
never drift from the real contract.

Run from the repo root:  apps/api/.venv/Scripts/python.exe scripts/export_operation_certs.py
(requires the api venv + a reachable dev database; import path is apps/api).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "api"))

TEMPLATE = REPO / "scripts" / "operation-certs.template.html"
OUTPUT = REPO / "docs" / "operation-certs.html"


def _verdict(raw: str) -> str:
    v = str(raw).lower()
    if v in ("not_applicable", "na", "n/a"):
        return "na"
    return "PASS" if v == "pass" else "FAIL" if v == "fail" else str(raw).upper()


def _dims(results: list[dict]) -> list:
    out = []
    for r in results:
        v = _verdict(r.get("verdict", ""))
        out.append([r.get("dimension", ""), v, r.get("score"), r.get("threshold")])
    return out


def _short_date(iso: str | None) -> str | None:
    return iso.split("T")[0] if iso else None


async def build() -> dict:
    from src.db import SessionLocal  # noqa: E402
    from src.models.forge_instruction_set import ForgeInstructionSet  # noqa: E402
    from src.services.operation import views  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    async with SessionLocal() as s:
        sbs = await views.side_by_side(s)
        cov = await views.coverage(s)
        cap = await views.capacity(s)
        # Declared instruction hashes (persisted at curriculum submission) — used to show the
        # declared-vs-ran comparison on a VOID; absent for modules never submitted (shown as such).
        declared: dict[tuple[str, str], str] = {}
        for iset in (await s.execute(select(ForgeInstructionSet))).scalars().all():
            declared.setdefault((iset.forgeId, iset.moduleId), iset.contentHash)

        items = []
        for it in sbs["items"]:
            op = it["operation"]
            data_op = {
                "state": op["state"],
                "tier": op["max_certified_trust_tier"],
                "fc": op["functions_certified"],
                "fim": op["functions_in_module"],
                "spread": op["rubric_dimension_spread"] or 0.0,
                "dims": _dims(op["operation_rubric_results"]),
                "scen": [
                    [r["scenario_class"], _verdict(r["verdict"])]
                    for r in op["per_scenario_class_results"]
                ],
                "fmodes": op["failure_modes_observed"],
                "instr": op["instruction_version"],
                "api": op["forge_api_version"],
            }
            if op["state"] == "revoked":
                ran = op["instruction_content_hash"]
                dec = declared.get((op["forge_id"], op["module_id"]))
                data_op["void"] = {"ran": ran, "declared": dec if dec and dec != ran else None}
            dom = it["domain"]
            data_dom = (
                {
                    "present": True,
                    "state": dom["state"],
                    "tier": dom["tier"],
                    "ver": dom["rubric_version"],
                    "issued": _short_date(dom["issued_at"]),
                    "expires": _short_date(dom["expires_at"]),
                    "total": dom["dimensions_total"],
                }
                if dom["present"]
                else {"present": False}
            )
            items.append(
                {
                    "agent": it["agent_name"],
                    "vid": it["agent_village_id"],
                    "cap": it["capability_label"],
                    "module": it["module_id"],
                    "op": data_op,
                    "domain": data_dom,
                }
            )

        forge = cov["forges"][0] if cov["forges"] else {"forge_label": "—", "modules": []}
        coverage = {
            "forge": forge.get("forge_label", "—"),
            "covered": forge.get("modules_covered", 0),
            "total": forge.get("modules_in_forge", 0),
            "thr": cov["thin_coverage_threshold"],
            "note": cov.get("coverage_note", ""),
            # [label, best-single-agent (union lower bound), denominator, thin, certified-agents]
            "modules": [
                [
                    m["module_label"],
                    m["best_single_agent_functions"],
                    m["functions_in_module"],
                    m["thin"],
                    m["certified_agents"],
                ]
                for m in forge.get("modules", [])
            ],
        }
        capacity = {
            "free": cap["totals"]["certified_free"],
            "allocated": cap["totals"]["certified_allocated"],
            "produced": cap["totals"]["produced_not_certified"],
        }
        depts_raw = await views.dept_context(s)
        depts = [
            {
                "key": d["department_key"],
                "forge": d["forge_label"],
                "context": d["forge_context"],
                "venture": d["venture_context"],
                "state": d["state"],
                "esc": d["escalation_path_verified"],
                "comp": d["compliance_coupling_verified"],
            }
            for d in depts_raw["items"]
        ]

        from src.services.incident.report import incident_report  # noqa: E402

        rep = await incident_report(s)
        incidents = [
            {"kind": i.get("kind", ""), "label": i.get("summary", ""), "n": i.get("count", 0),
             "note": i.get("kind", "")}
            for i in rep.get("incidents", [])
            if i.get("severity") == "high"
        ]

    return {
        "items": items,
        "coverage": coverage,
        "capacity": capacity,
        "depts": depts,
        "incidents": incidents,
    }


def write_export(data: dict) -> int:
    """Inject `data` into the template and write docs/operation-certs.html. Returns byte count."""
    template = TEMPLATE.read_text(encoding="utf-8")
    payload = "const DATA = " + json.dumps(data, indent=2) + ";"
    html = template.replace("const DATA = /*__DATA__*/ null;", payload)
    if "const DATA = /*__DATA__*/ null;" in html or "__DATA__" in html:
        raise SystemExit("placeholder not substituted — template markers changed?")
    OUTPUT.write_text(html, encoding="utf-8")
    return len(html)


def main() -> None:
    data = asyncio.run(build())
    n = write_export(data)
    print(f"wrote {OUTPUT} ({n:,} bytes) · {len(data['items'])} agent×capability cards")


if __name__ == "__main__":
    main()
