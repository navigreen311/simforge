// PDP authorization decision pill (blueprint §F.6; ADR-0024).

const STYLES: Record<string, string> = {
  allow: "bg-success/15 text-success",
  deny: "bg-danger/15 text-danger",
  step_up_approval_required: "bg-warning/20 text-warning",
  downgrade_and_retry: "bg-info/15 text-info",
};

const LABELS: Record<string, string> = {
  allow: "Allow",
  deny: "Deny",
  step_up_approval_required: "Step-up",
  downgrade_and_retry: "Downgrade",
};

export function DecisionPill({ decision }: { decision: string }) {
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-semibold ${STYLES[decision] ?? "bg-ink-600 text-ink-100"}`}
    >
      {LABELS[decision] ?? decision}
    </span>
  );
}
