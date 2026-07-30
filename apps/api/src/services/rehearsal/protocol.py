"""Dress Rehearsal Protocol (§15).

Computes the entry + exit criteria for a pack's go-live rehearsal from live data, records a
DressRehearsal, and captures Ed25519-signed per-pack sign-offs. Criteria that depend on a real
production deployment (forge↔prod parity ≥0.90, human red-team passes) are configurable seams —
flagged `is_seam` so the gate is honest about what's measured vs assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.dress_rehearsal import DressRehearsal
from src.models.gap import SoftwareGap, VillageOSGap
from src.models.pack import Pack, Scenario
from src.models.run import Run
from src.models.scorecard import Scorecard
from src.models.village_fingerprint import VillageFingerprint
from src.utils.time import utcnow

# Entry thresholds (§15.1).
_MIN_PARITY = 0.90
_FINGERPRINT_STABLE_DAYS = 7
# Battery composition (§15.2).
_BATTERY_MIN = {"foundational": 10, "intermediate": 5, "advanced_crisis": 3}
_MIN_BLIND_PCT = 0.25


class RehearsalError(Exception):
    """Invalid rehearsal operation (unknown pack/rehearsal, bad sign-off)."""


@dataclass
class Criterion:
    name: str
    passed: bool
    detail: str
    is_seam: bool = False


@dataclass
class CriteriaResult:
    criteria: list[Criterion] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.criteria)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "criteria": [c.__dict__ for c in self.criteria],
        }


async def _pack(session: AsyncSession, pack_id: str) -> Pack:
    p = (await session.execute(select(Pack).where(Pack.packId == pack_id))).scalar_one_or_none()
    if p is None:
        raise RehearsalError(f"Pack not found: {pack_id}")
    return p


async def _p0_gap_count(session: AsyncSession) -> int:
    sw = (
        await session.execute(
            select(func.count())
            .select_from(SoftwareGap)
            .where(SoftwareGap.severity == "P0", SoftwareGap.status == "open")
        )
    ).scalar_one()
    vos = (
        await session.execute(
            select(func.count())
            .select_from(VillageOSGap)
            .where(VillageOSGap.severity == "P0", VillageOSGap.status == "open")
        )
    ).scalar_one()
    return int(sw) + int(vos)


async def check_entry_criteria(session: AsyncSession, pack_id: str) -> CriteriaResult:
    """§15.1 entry criteria, computed from live data (parity is a configurable seam)."""
    pack = await _pack(session, pack_id)
    res = CriteriaResult()

    # 1. Minimum pack coverage — scenarios present.
    scen_count = (
        await session.execute(
            select(func.count()).select_from(Scenario).where(Scenario.packId == pack.id)
        )
    ).scalar_one()
    res.criteria.append(Criterion("pack_has_scenarios", scen_count > 0, f"{scen_count} scenarios"))

    # 2. Pack signed by its owner_human (v1.0.0 sign-off).
    res.criteria.append(
        Criterion(
            "pack_signed",
            pack.signedBy is not None,
            f"signed by {pack.signedBy}" if pack.signedBy else "pack not signed",
        )
    )

    # 3. Forge↔prod parity ≥ 0.90 (SEAM — no production to compare in this repo).
    parity = settings.dress_rehearsal_forge_parity
    res.criteria.append(
        Criterion(
            "forge_parity",
            parity >= _MIN_PARITY,
            f"parity {parity:.2f} (min {_MIN_PARITY})",
            is_seam=True,
        )
    )

    # 4. Schema fingerprint stable ≥ 7 days.
    current = (
        await session.execute(
            select(VillageFingerprint).where(VillageFingerprint.isCurrent.is_(True))
        )
    ).scalar_one_or_none()
    if current is None:
        res.criteria.append(Criterion("fingerprint_stable", False, "no current fingerprint"))
    else:
        stable_days = (utcnow() - current.capturedAt).days
        res.criteria.append(
            Criterion(
                "fingerprint_stable",
                stable_days >= _FINGERPRINT_STABLE_DAYS,
                f"stable {stable_days}d (min {_FINGERPRINT_STABLE_DAYS})",
            )
        )

    # 5. Zero outstanding P0 gaps.
    p0 = await _p0_gap_count(session)
    res.criteria.append(Criterion("zero_p0_gaps", p0 == 0, f"{p0} open P0 gaps"))

    # 6. Constitution ratified.
    from src.services.governance.constitution import get_current_constitution

    const = await get_current_constitution(session)
    res.criteria.append(
        Criterion(
            "constitution_ratified",
            const is not None,
            f"active {const.version}" if const else "none ratified",
        )
    )
    return res


async def check_exit_criteria(session: AsyncSession, pack_id: str) -> CriteriaResult:
    """§15.5 exit criteria from the pack's runs (red-team pass count is a configurable seam)."""
    pack = await _pack(session, pack_id)
    res = CriteriaResult()

    runs = (await session.execute(select(Run).where(Run.packId == pack.id))).scalars().all()
    run_ids = [r.id for r in runs]
    cards = (
        (await session.execute(select(Scorecard).where(Scorecard.runId.in_(run_ids or ["none"]))))
        .scalars()
        .all()
    )

    # 1. At least one run scored + gate passed.
    passed_cards = [c for c in cards if c.readinessGatePassed]
    res.criteria.append(
        Criterion("gate_passed", len(passed_cards) > 0, f"{len(passed_cards)} gate-passing runs")
    )
    # 2. Zero compliance violations among the pack's runs.
    violations = sum(1 for c in cards if c.p2Compliance is False)
    res.criteria.append(
        Criterion("zero_compliance_violations", violations == 0, f"{violations} P2 violations")
    )
    # 3. Zero outstanding P0 gaps.
    p0 = await _p0_gap_count(session)
    res.criteria.append(Criterion("zero_p0_gaps", p0 == 0, f"{p0} open P0 gaps"))
    # 4. Blind-mode minimum across the pack's runs (§15.3).
    total = len(runs)
    blind = sum(1 for r in runs if r.blindMode)
    ratio = (blind / total) if total else 0.0
    res.criteria.append(
        Criterion(
            "blind_mode_minimum",
            ratio >= _MIN_BLIND_PCT,
            f"{blind}/{total} blind ({ratio:.0%}, min {_MIN_BLIND_PCT:.0%})",
        )
    )
    # 5. Human red-team pass (§15.4) — SEAM (configurable count; ≥2 required).
    passes = settings.dress_rehearsal_redteam_passes
    res.criteria.append(
        Criterion("red_team_passed", passes >= 2, f"{passes} red-team passes (min 2)", is_seam=True)
    )
    return res


async def start_rehearsal(session: AsyncSession, pack_id: str) -> DressRehearsal:
    await _pack(session, pack_id)
    entry = await check_entry_criteria(session, pack_id)
    r = DressRehearsal(
        packId=pack_id,
        status="entry_passed" if entry.passed else "entry_failed",
        entryResults=entry.as_dict(),
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r


async def run_exit(session: AsyncSession, rehearsal_id: str) -> DressRehearsal:
    r = (
        await session.execute(select(DressRehearsal).where(DressRehearsal.id == rehearsal_id))
    ).scalar_one_or_none()
    if r is None:
        raise RehearsalError(f"Rehearsal not found: {rehearsal_id}")
    if r.status not in ("entry_passed", "exit_failed"):
        raise RehearsalError(f"Cannot run exit from status {r.status} (entry must pass first)")
    exit_res = await check_exit_criteria(session, r.packId)
    r.exitResults = exit_res.as_dict()
    r.status = "exit_passed" if exit_res.passed else "exit_failed"
    await session.commit()
    await session.refresh(r)
    return r


async def sign_off(
    session: AsyncSession, rehearsal_id: str, *, role: str, signer_id: str
) -> DressRehearsal:
    """Record an Ed25519-signed per-pack sign-off (§15.6). Requires exit criteria to have passed."""
    r = (
        await session.execute(select(DressRehearsal).where(DressRehearsal.id == rehearsal_id))
    ).scalar_one_or_none()
    if r is None:
        raise RehearsalError(f"Rehearsal not found: {rehearsal_id}")
    if r.status not in ("exit_passed", "signed"):
        raise RehearsalError("Exit criteria must pass before sign-off")

    from src.services.cert.signer import encode_signature, get_signer

    now = utcnow()
    payload = f"{r.id}|{r.packId}|{role}|{signer_id}|{now.isoformat()}"
    signer = get_signer()
    signature = encode_signature(signer.sign(payload.encode()))
    signoffs = list(r.signoffs or [])
    signoffs.append(
        {
            "role": role,
            "signer": signer_id,
            "signature": signature,
            "signing_key_id": signer.key_id(),
            "at": now.isoformat(),
        }
    )
    r.signoffs = signoffs
    r.status = "signed"
    await session.commit()
    await session.refresh(r)
    return r
