// Run execution-status badge (passed/failed/errored/running/pending).

const STYLES: Record<string, string> = {
  passed: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  errored: "bg-danger/25 text-danger",
  running: "bg-info/15 text-info",
  pending: "bg-ink-500 text-ink-100",
  cancelled: "bg-ink-500 text-ink-200",
};

export function RunStatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${STYLES[status] ?? "bg-ink-500"}`}>
      {status}
    </span>
  );
}
