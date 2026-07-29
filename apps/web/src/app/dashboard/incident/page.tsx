import Link from "next/link";

import { PageMeta } from "@/components/ui/PageMeta";
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

// Plain-language meaning + next step per incident type code (keyed by `kind`).
const INCIDENT_TYPES: Record<string, { explain: string; whatToDo: string }> = {
  certs_revoked: {
    explain:
      "Certificates permanently withdrawn. Agents that relied on these are no longer certified for those capabilities and should not perform them.",
    whatToDo:
      "Review these agents' certifications. If the revocation is demo/seed data, it can be cleared; if real, the agents must be re-certified before operating these capabilities.",
  },
  certs_suspended: {
    explain:
      "Certificates temporarily paused. Affected agents are not currently certified for these capabilities until the certs are active again.",
    whatToDo:
      "Review these agents' certifications. If the suspension is demo/seed data, it can be cleared; if real, the agents must be re-certified before operating these capabilities.",
  },
  gaps_p0: {
    explain:
      "Top-severity software defects surfaced by scenario runs. P0 means highest priority — these can block or corrupt the work.",
    whatToDo:
      "Review these gaps on the Gaps page; the P0s should be triaged first. Several may share a single root cause (see the situation summary).",
  },
  gaps_p1: {
    explain: "High-severity software defects. Important but below P0.",
    whatToDo:
      "Review these gaps on the Gaps page. Several may share a single root cause (see the situation summary).",
  },
  safe_mode: {
    explain:
      "Emergency safe mode is active — the platform has halted operations in the named domains.",
    whatToDo: "Address the trigger, then deactivate safe mode from Governance once resolved.",
  },
  budget_sandbox: {
    explain: "Sandbox monthly spend has exceeded its cap.",
    whatToDo: "Review sandbox run volume; raise the cap or pause runs.",
  },
  budget_integrated: {
    explain: "Integrated (real-Forge) monthly spend has exceeded its cap.",
    whatToDo: "Review integrated run volume; raise the cap or pause integrated runs.",
  },
};

function humanize(kind: string): string {
  return kind.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function typeInfo(kind: string) {
  return (
    INCIDENT_TYPES[kind] ?? {
      explain: `${humanize(kind)}. (No plain-language description is catalogued for this type yet.)`,
      whatToDo: "Review the affected entities below.",
    }
  );
}

function LinkChip({
  href,
  text,
  title,
  tone = "neutral",
}: {
  href: string;
  text: string;
  title?: string;
  tone?: "neutral" | "phi";
}) {
  const cls = tone === "phi" ? "bg-danger/15 text-danger" : "bg-ink-700 text-ink-100";
  return (
    <Link href={href} title={title} className={`rounded px-2 py-0.5 text-[11px] ${cls} hover:underline`}>
      {text}
    </Link>
  );
}

function AffectedGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="text-[10px] uppercase tracking-wide text-ink-400">{label}</span>
      {children}
    </div>
  );
}

function IncidentCard({ inc }: { inc: Incident }) {
  const b = inc.blast_radius;
  const info = typeInfo(inc.kind);
  const scoped = b.agents.length + b.forge_caps.length + b.departments.length > 0;
  const radiusSentence =
    `${b.forge_caps.length} capabilit${b.forge_caps.length === 1 ? "y" : "ies"}` +
    (b.agents.length ? ` across ${b.agents.length} agent${b.agents.length === 1 ? "" : "s"}` : "") +
    (b.departments.length
      ? ` in ${b.departments.length} department${b.departments.length === 1 ? "" : "s"}`
      : "") +
    " affected.";

  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-4">
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 rounded px-2 py-0.5 text-xs font-semibold ${SEV[inc.severity] ?? "bg-ink-600"}`}>
          {inc.severity}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-ink-50">{inc.summary}</div>
          <p className="mt-1 text-xs text-ink-300">{info.explain}</p>
        </div>
        <span
          className="shrink-0 font-mono text-[10px] text-ink-500"
          title="Raw incident type code"
        >
          {inc.kind}
        </span>
      </div>

      {inc.demo_driven && (
        <div className="mt-2 rounded border border-info/30 bg-info/5 px-2 py-1 text-[11px] text-info">
          Driven by seed/demo data — not a production outage.
        </div>
      )}

      {scoped && (
        <div className="mt-3 flex flex-col gap-1.5">
          <div className="text-[11px] text-ink-400">{radiusSentence}</div>
          {b.forge_caps.length > 0 && (
            <AffectedGroup label="Capabilities affected">
              {b.forge_caps.map((c) => (
                <LinkChip
                  key={c}
                  href="/dashboard/certs"
                  text={inc.cap_labels[c]?.label ?? c}
                  title={c}
                />
              ))}
            </AffectedGroup>
          )}
          {b.agents.length > 0 && (
            <AffectedGroup label="Agents affected">
              {b.agents.map((a) => (
                <LinkChip
                  key={a}
                  href={`/dashboard/runs?agent=${a}`}
                  text={inc.agent_names[a] ?? a}
                  title={a}
                />
              ))}
            </AffectedGroup>
          )}
          {b.departments.length > 0 && (
            <AffectedGroup label="Departments affected">
              {b.departments.map((d) => (
                <LinkChip key={d} href="/dashboard/departments" text={d} />
              ))}
            </AffectedGroup>
          )}
        </div>
      )}

      <div className="mt-3 rounded border border-ink-600 bg-ink-900 px-3 py-2 text-xs">
        <span className="font-semibold text-ink-300">What to do: </span>
        <span className="text-ink-200">{info.whatToDo}</span>
      </div>
    </div>
  );
}

function situationLines(incidents: Incident[]): string[] {
  const total = incidents.length;
  const names: Record<string, string> = {};
  for (const inc of incidents) Object.assign(names, inc.agent_names);

  // Agent overlap across incidents.
  const agentKinds = new Map<string, Set<string>>();
  for (const inc of incidents)
    for (const a of inc.blast_radius.agents) {
      if (!agentKinds.has(a)) agentKinds.set(a, new Set());
      agentKinds.get(a)!.add(inc.kind);
    }
  const shared = [...agentKinds.entries()]
    .filter(([, ks]) => ks.size >= 2)
    .sort((a, b) => b[1].size - a[1].size);

  // Gap forge clustering.
  const gaps = incidents.filter((i) => i.kind.startsWith("gaps_"));
  const forgeCount = new Map<string, number>();
  for (const g of gaps) for (const f of g.blast_radius.forge_caps) forgeCount.set(f, (forgeCount.get(f) ?? 0) + 1);
  const sharedForges = [...forgeCount.entries()].filter(([, n]) => n >= 2).map(([f]) => f);

  const lines: string[] = [];
  if (shared.length > 0) {
    const [agent, kinds] = shared[0];
    lines.push(
      `${kinds.size} of ${total} incidents trace to a single agent (${names[agent] ?? agent}) whose certificates are revoked or suspended — this appears to be one situation, not ${total} independent failures. (inferred from shared blast radius)`,
    );
  }
  if (sharedForges.length > 0) {
    lines.push(
      `The open software gaps concentrate in ${sharedForges.join(", ")} — likely a shared root cause across the P0/P1 gaps. (inferred)`,
    );
  }
  return lines;
}

function BudgetBar({ mode, m }: { mode: string; m: { spent_usd: number; cap_usd: number; exceeded: boolean } }) {
  const pct = m.cap_usd > 0 ? Math.min(100, (m.spent_usd / m.cap_usd) * 100) : m.spent_usd > 0 ? 100 : 0;
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-4">
      <div className="flex items-baseline justify-between text-sm">
        <span className="capitalize text-ink-100">{mode}</span>
        <span className="font-mono text-xs text-ink-300">
          ${m.spent_usd.toFixed(2)} / ${m.cap_usd.toFixed(2)}
        </span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-ink-600">
        <div className={`h-full ${m.exceeded ? "bg-danger" : "bg-gold-500"}`} style={{ width: `${pct}%` }} />
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

  const lines = report ? situationLines(report.incidents) : [];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Incident Command</h1>
        <PageMeta />
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        What&apos;s wrong right now and how big is the blast radius — derived live from safe mode,
        invalidated certs, open high-severity gaps, and cost caps (ADR-0040). Each incident is a
        derived condition, not a hand-filed ticket.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load incident status: <code className="text-danger">{error}</code>
        </div>
      ) : report ? (
        <>
          <div
            className={`mb-4 flex items-center gap-3 rounded-xl border p-4 ${
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
            <div className="mb-4 rounded-xl border border-danger/50 bg-danger/15 p-4 text-sm text-ink-50">
              <strong className="text-danger">SAFE MODE ACTIVE</strong> — {report.safe_mode.reason}
              {report.safe_mode.activated_by && ` (by ${report.safe_mode.activated_by})`}
            </div>
          )}

          {lines.length > 0 && (
            <div className="mb-6 rounded-xl border border-warning/40 bg-warning/10 p-4">
              <h2 className="mb-1 text-sm font-semibold text-warning">Situation summary</h2>
              <p className="mb-2 text-xs text-ink-300">
                Why the board reads <strong>{report.status}</strong>, in plain terms. Connections
                below are inferred from shared blast radius — they are likely, not confirmed.
              </p>
              <ul className="flex list-disc flex-col gap-1 pl-5 text-xs text-ink-100">
                {lines.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
          )}

          <section className="mb-8">
            <h2 className="mb-2 text-lg">This month&apos;s spend</h2>
            <p className="mb-3 text-xs text-ink-400">
              Sandbox runs cost against a $50/mo cap; integrated runs (real Forge calls) against a
              $500/mo cap.{" "}
              {Object.values(report.budget.modes).every((m) => m.spent_usd === 0)
                ? "Both at $0 this month — nowhere near a cap."
                : "See the bars for current spend against each cap."}
            </p>
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
