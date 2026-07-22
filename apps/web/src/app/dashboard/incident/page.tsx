import { incident, type Incident, type IncidentReport } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const SEV: Record<string, string> = {
  critical: "bg-danger/20 text-danger",
  high: "bg-warning/20 text-warning",
  medium: "bg-info/15 text-info",
};

const STATUS_STYLE: Record<string, string> = {
  ok: "border-success/40 bg-success/10 text-success",
  degraded: "border-warning/40 bg-warning/10 text-warning",
  critical: "border-danger/50 bg-danger/15 text-danger",
};

function Chips({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="text-[10px] uppercase tracking-wide text-ink-400">{label}</span>
      {items.map((x) => (
        <span key={x} className="rounded bg-ink-700 px-2 py-0.5 font-mono text-[11px] text-ink-100">
          {x}
        </span>
      ))}
    </div>
  );
}

function IncidentCard({ inc }: { inc: Incident }) {
  const b = inc.blast_radius;
  const empty = !b.agents.length && !b.forge_caps.length && !b.departments.length;
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-4">
      <div className="flex items-center gap-3">
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${SEV[inc.severity] ?? "bg-ink-600"}`}>
          {inc.severity}
        </span>
        <span className="text-sm text-ink-50">{inc.summary}</span>
        <span className="ml-auto font-mono text-[11px] text-ink-400">{inc.kind}</span>
      </div>
      <div className="mt-2 flex flex-col gap-1">
        {empty ? (
          <span className="text-[11px] text-ink-400">no scoped blast radius</span>
        ) : (
          <>
            <Chips label="agents" items={b.agents} />
            <Chips label="caps" items={b.forge_caps} />
            <Chips label="depts" items={b.departments} />
          </>
        )}
      </div>
    </div>
  );
}

function BudgetBar({ mode, m }: { mode: string; m: { spent_usd: number; cap_usd: number; exceeded: boolean } }) {
  const pct = m.cap_usd > 0 ? Math.min(100, (m.spent_usd / m.cap_usd) * 100) : m.spent_usd > 0 ? 100 : 0;
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-4">
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink-100 capitalize">{mode}</span>
        <span className="font-mono text-xs text-ink-300">
          ${m.spent_usd.toFixed(2)} / ${m.cap_usd.toFixed(2)}
        </span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-ink-600">
        <div
          className={`h-full ${m.exceeded ? "bg-danger" : "bg-gold-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default async function IncidentPage() {
  let report: IncidentReport | null = null;
  let error: string | null = null;
  try {
    report = await incident.status();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load incident status";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Incident Command</h1>
      <p className="mb-6 text-ink-200">
        What&apos;s wrong right now and how big is the blast radius — derived live from safe mode,
        invalidated certs, open high-severity gaps, and cost caps (ADR-0040).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load incident status: <code className="text-danger">{error}</code>
        </div>
      ) : report ? (
        <>
          <div
            className={`mb-6 flex items-center gap-3 rounded-xl border p-4 ${
              STATUS_STYLE[report.status] ?? "border-ink-500 bg-ink-800 text-ink-100"
            }`}
          >
            <span className="text-lg font-semibold uppercase">{report.status}</span>
            <span className="text-sm">
              {report.total_incidents} incident{report.total_incidents === 1 ? "" : "s"} ·{" "}
              {report.counts.critical} critical · {report.counts.high} high · {report.counts.medium} medium
            </span>
          </div>

          {report.safe_mode.active && (
            <div className="mb-6 rounded-xl border border-danger/50 bg-danger/15 p-4 text-sm text-ink-50">
              <strong className="text-danger">SAFE MODE ACTIVE</strong> — {report.safe_mode.reason}
              {report.safe_mode.activated_by && ` (by ${report.safe_mode.activated_by})`}
            </div>
          )}

          <section className="mb-8">
            <h2 className="mb-3 text-lg">This month&apos;s spend</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {Object.entries(report.budget.modes).map(([mode, m]) => (
                <BudgetBar key={mode} mode={mode} m={m} />
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-lg">Active incidents</h2>
            {report.incidents.length === 0 ? (
              <div className="rounded-lg border border-success/30 bg-success/5 p-6 text-ink-100">
                No active incidents — safe mode off, no invalidated certs, no open P0/P1 gaps, budgets
                within cap.
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {report.incidents.map((inc) => (
                  <IncidentCard key={inc.kind} inc={inc} />
                ))}
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
