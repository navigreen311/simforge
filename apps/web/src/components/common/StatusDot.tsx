// Colored status dot — active/expired/revoked/suspended/ok/degraded (blueprint §D.3).

const COLORS: Record<string, string> = {
  ok: "bg-success",
  active: "bg-success",
  degraded: "bg-warning",
  suspended: "bg-warning",
  expired: "bg-ink-300",
  revoked: "bg-danger",
  error: "bg-danger",
};

export function StatusDot({ status, label }: { status: string; label?: string }) {
  const color = COLORS[status] ?? "bg-ink-300";
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} aria-hidden />
      {label && <span className="text-sm text-ink-100">{label}</span>}
    </span>
  );
}
