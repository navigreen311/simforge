// Plain-language PDP vocabulary — the four outcomes, the reason codes, and which factor drove a
// decision. Shared by the Policy page + the Decision explorer (one source, no duplication). The PDP
// returns only a final decision + reason code + detail (no step-by-step trace), so the driving
// factor is DERIVED from the reason code here.

export const DECISION_LABEL: Record<string, string> = {
  allow: "Allow",
  deny: "Deny",
  step_up_approval_required: "Step-up",
  downgrade_and_retry: "Downgrade",
};

export const DECISION_MEANING: Record<string, string> = {
  allow: "The agent is certified and permitted to perform this action.",
  deny: "The agent is not permitted — usually because the cert is missing, revoked, suspended, or expired.",
  step_up_approval_required:
    "Permitted, but requires an additional check/approval before proceeding.",
  downgrade_and_retry:
    "The agent's autonomy is reduced for this action — it may proceed at a lower level.",
};

export const REASON_CATALOG: Record<string, string> = {
  cert_revoked: "The certificate for this capability was permanently withdrawn.",
  cert_suspended: "The certificate for this capability is temporarily paused.",
  cert_expired: "The certificate for this capability has expired.",
  no_certification: "The agent holds no certificate for this capability.",
  unknown_subject: "No such agent is registered.",
  safe_mode_active: "Emergency safe mode is active — every action needs human approval.",
  autonomy_sufficient: "Active certificate and the agent's autonomy is high enough to act.",
  approval_required_l3: "Autonomy L3 — execution requires human approval first.",
  draft_only_l2: "Autonomy L2 — the agent may draft for review, not take a live action.",
  observe_only_l1: "Autonomy L1 — observe only; not cleared to act.",
};

function humanize(code: string): string {
  return code.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function reasonText(code: string): string {
  return REASON_CATALOG[code] ?? `${humanize(code)} (no plain-language description catalogued).`;
}

export function isReasonCatalogued(code: string): boolean {
  return code in REASON_CATALOG;
}

export type DrivingFactor = "Certification" | "Autonomy" | "Safe mode" | "Subject" | "—";

// Which input drove the decision — derived from the reason code (the PDP emits no trace).
export function drivingFactor(code: string): DrivingFactor {
  if (code.startsWith("cert_") || code === "no_certification") return "Certification";
  if (code === "safe_mode_active") return "Safe mode";
  if (code === "unknown_subject") return "Subject";
  if (["autonomy_sufficient", "approval_required_l3", "draft_only_l2", "observe_only_l1"].includes(code))
    return "Autonomy";
  return "—";
}
