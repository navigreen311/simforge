// Presentation helpers for Forge Operation Certification (Batch 6).
// Pure — labels, tones, and small derivations only. Keeps JSX pages thin and
// guarantees the 7 states render as VISIBLY DISTINCT (never a low score):
// never_certified (blue, "not run") ≠ failed (red) ≠ stale (amber) — spec Batch 6.

import type {
  OperationCertState,
  OperationDimensionVerdict,
  OperationScenarioClass,
  OperationTrustTier,
} from "@/lib/api/client";

export interface StateMeta {
  label: string;
  // Tailwind classes for a chip. Distinct hue per meaning:
  //  green = earned, red = ran-and-failed / void, blue = never ran,
  //  gold = in progress, amber = was valid but curriculum/forge moved.
  chip: string;
  dot: string;
  blurb: string;
}

export const OPERATION_STATE_META: Record<OperationCertState, StateMeta> = {
  certified: {
    label: "Certified",
    chip: "bg-success/15 text-success border border-success/40",
    dot: "bg-success",
    blurb: "Earned against the current instruction set and operation rubric.",
  },
  provisional: {
    label: "Provisional",
    // Distinct from certified (green) and failed (red): passed the bar but held. A slate/violet
    // hue with a dashed border reads as "not final" without implying failure or a low score.
    chip: "bg-accent/15 text-accent border border-dashed border-accent/50",
    dot: "bg-accent",
    blurb:
      "Passed the threshold, but the rubric dimensions collapsed (measured too similarly to " +
      "trust) or a required never-do dimension went untested — full certification withheld until " +
      "real signal separates them. Not assignable.",
  },
  in_training: {
    label: "In training",
    chip: "bg-gold-500/15 text-gold-300 border border-gold-600/40",
    dot: "bg-gold-400",
    blurb: "Producing evidence; not yet certified. SimForge-owned, not assignable.",
  },
  never_certified: {
    label: "Never certified",
    // Blue, NOT red — a run that never happened is not a run that scored badly.
    chip: "bg-info/15 text-info border border-info/40",
    dot: "bg-info",
    blurb: "No operation run has happened for this module. Not a failure — no attempt yet.",
  },
  failed: {
    label: "Failed",
    chip: "bg-danger/15 text-danger border border-danger/40",
    dot: "bg-danger",
    blurb: "Ran and did not meet threshold. Distinct from never-run; not a low score.",
  },
  stale_instructions: {
    label: "Stale — instructions",
    chip: "bg-warning/15 text-warning border border-warning/40",
    dot: "bg-warning",
    blurb: "Instructions were rewritten since this cert. Re-cert required; not assignable.",
  },
  stale_forge: {
    label: "Stale — Forge",
    // Amber like stale_instructions (both mean "re-cert required") but a distinct
    // label and a dashed dot treatment so the cause reads at a glance.
    chip: "bg-warning/10 text-warning border border-dashed border-warning/50",
    dot: "bg-warning ring-2 ring-warning/30",
    blurb: "The Forge released a change affecting this module. Re-cert required; not assignable.",
  },
  revoked: {
    label: "Revoked / VOID",
    // Strong red with a ring to separate it from an ordinary failure.
    chip: "bg-danger/25 text-danger border border-danger/60 ring-1 ring-danger/50",
    dot: "bg-danger ring-2 ring-danger/40",
    blurb: "Content-hash mismatch or traced misoperation VOIDED this cert (HIGH incident).",
  },
};

const TRUST_TIER_LABEL: Record<OperationTrustTier, string> = {
  auto_execute: "Auto-execute",
  propose: "Propose",
  suggest: "Suggest",
};

export function trustTierLabel(tier: OperationTrustTier | null): string {
  return tier ? TRUST_TIER_LABEL[tier] : "—";
}

export interface VerdictMeta {
  label: string;
  chip: string;
}

export const VERDICT_META: Record<OperationDimensionVerdict, VerdictMeta> = {
  PASS: { label: "PASS", chip: "bg-success/15 text-success" },
  FAIL: { label: "FAIL", chip: "bg-danger/15 text-danger" },
  NOT_RUN: { label: "not run", chip: "bg-info/10 text-info" },
  NOT_APPLICABLE: { label: "n/a", chip: "bg-ink-600 text-ink-200" },
};

// The payload contract carries verdicts in mixed case (e.g. `not_applicable` lowercase). Look them
// up case-insensitively and fall back to a neutral chip so an unknown verdict never crashes render.
export function verdictMeta(verdict: string): VerdictMeta {
  const key = String(verdict).toUpperCase() as OperationDimensionVerdict;
  return VERDICT_META[key] ?? { label: String(verdict), chip: "bg-ink-600 text-ink-200" };
}

// Plain-language names for the operation rubric dimensions (proposal §5 dims).
// `protocol_conformance` is the CHANNEL dimension (ADR-0052) and reads differently from the other
// five on purpose: they say what the agent did, it says whether the answer could be read at all.
const DIMENSION_LABEL: Record<string, string> = {
  sequence_correctness: "Correct operation order",
  failure_recognition: "Recognises failures",
  escalation_discipline: "Escalates when it should",
  never_do_adherence: "Refuses never-do actions",
  recovery: "Recovers correctly after a failure",
  protocol_conformance: "Answers in the required format",
};

export function dimensionLabel(dim: string): string {
  return DIMENSION_LABEL[dim] ?? dim;
}

const SCENARIO_CLASS_LABEL: Record<OperationScenarioClass, string> = {
  happy_path: "Happy path",
  malformed_input: "Malformed input",
  partial_failure: "Partial failure",
  silent_failure: "Silent failure",
  rate_limited: "Rate limited",
  permission_denied: "Permission denied",
  never_do_violation: "Never-do violation",
  escalation_required: "Escalation required",
  recovery_after_failure: "Recovery after failure",
};

export function scenarioClassLabel(cls: OperationScenarioClass): string {
  return SCENARIO_CLASS_LABEL[cls] ?? cls;
}

// Collapse threshold for rubric_dimension_spread — mirrors Meta-Eval's
// low-information warning. Near-zero spread across dims that SHOULD differ =
// "measuring one thing five times". Non-blocking; shown beside the PASS.
export const COLLAPSE_SPREAD_THRESHOLD = 0.02;

/**
 * A passed result whose dimensions collapsed → low-information warning. Fires for `provisional`
 * (the state a collapse now HOLDS the cert at) as well as `certified` — the warning explains WHY a
 * cert is provisional. Non-blocking; advisory only.
 */
export function isSpreadCollapsed(
  state: OperationCertState,
  spread: number | null,
  numericDimCount: number,
): boolean {
  return (
    (state === "certified" || state === "provisional") &&
    spread !== null &&
    numericDimCount >= 2 &&
    spread < COLLAPSE_SPREAD_THRESHOLD
  );
}
