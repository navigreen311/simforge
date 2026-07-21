const STYLES: Record<string, string> = {
  P0: "bg-danger/25 text-danger",
  P1: "bg-warning/20 text-warning",
  P2: "bg-ink-600 text-ink-100",
};

export function SeverityPill({ severity }: { severity: string }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STYLES[severity] ?? "bg-ink-600"}`}>
      {severity}
    </span>
  );
}
