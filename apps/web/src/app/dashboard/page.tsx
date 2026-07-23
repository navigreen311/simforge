import Link from "next/link";

import { AutonomyLadderIndicator } from "@/components/agents/AutonomyLadderIndicator";
import { SeverityPill } from "@/components/gaps/SeverityPill";
import { Sparkline } from "@/components/ui/Sparkline";
import {
  api,
  dashboard,
  gaps,
  health,
  type AgentSummary,
  type DashboardSummary,
  type IntegrityWarning,
  type SoftwareGap,
  type SystemStatus,
} from "@/lib/api/client";

// Data-heavy read page — always dynamic (blueprint §D.2).
export const dynamic = "force-dynamic";

function StatTile({
  label,
  value,
  hint,
  warn,
  children,
}: {
  label: string;
  value: string | number;
  hint?: string;
  warn?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <div className="flex items-center gap-2 text-sm text-ink-200">
        {warn && <span className="h-2 w-2 rounded-full bg-danger" aria-label="warning" />}
        {label}
      </div>
      <div className="mt-2 font-display text-3xl text-gold-500">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-300">{hint}</div>}
      {children}
    </div>
  );
}

export default async function OverviewPage() {
  let agents: AgentSummary[] = [];
  let agentTotal = 0;
  let deptTotal = 0;
  let apiStatus = "error";
  let topGaps: SoftwareGap[] = [];
  let summary: DashboardSummary | null = null;
  let system: SystemStatus | null = null;
  let warnings: IntegrityWarning[] = [];
  let series: number[] = [];
  let loadError: string | null = null;

  try {
    const [agentList, deptList, ready, gapList, sum, sys, integ, rpd] = await Promise.all([
      api.agents({ page_size: 50 }),
      api.departments(),
      api.ready(),
      gaps.software(),
      dashboard.summary(),
      health.systemStatus(),
      dashboard.integrityWarnings(),
      dashboard.runsPerDay(14),
    ]);
    agents = agentList.items;
    agentTotal = agentList.total;
    deptTotal = deptList.total;
    apiStatus = ready.status;
    topGaps = gapList.items.slice(0, 5);
    summary = sum;
    system = sys;
    warnings = integ.warnings;
    series = rpd.series.map((p) => p.count);
  } catch (e) {
    loadError = e instanceof Error ? e.message : "Failed to reach the API";
  }

  const certWarn = !!summary && summary.issued_certs > 0 && summary.active_certs === 0;

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Overview</h1>
      <p className="mb-6 text-ink-200">Village certification readiness at a glance.</p>

      {loadError ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-ink-50">
          Could not load data from the API: <code className="text-danger">{loadError}</code>
          <div className="mt-1 text-ink-300">
            Is the backend running at <code>{process.env.NEXT_PUBLIC_API_URL}</code>? Try{" "}
            <code>pnpm --filter api dev</code>.
          </div>
        </div>
      ) : (
        <>
          {/* Governance-integrity warnings (autonomy without cert backing). */}
          {warnings.length > 0 && (
            <div className="mb-6 rounded-xl border border-danger/50 bg-danger/15 p-4 text-sm text-ink-50">
              <div className="font-semibold text-danger">
                ⚠ Autonomy Ladder inconsistency ({warnings.length})
              </div>
              <ul className="mt-2 flex flex-col gap-1">
                {warnings.map((w) => (
                  <li key={w.agent_id}>
                    <span className="font-mono text-xs">{w.agent_id}</span> at{" "}
                    <strong>{w.autonomy_level}</strong> with {w.active_certs} active certs —
                    auto-downgrade may not have fired.{" "}
                    <Link href={`/dashboard/policy`} className="text-gold-400 hover:underline">
                      investigate
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatTile label="Agents tracked" value={agentTotal} hint="from Village roster">
              {series.length > 0 && (
                <div className="mt-3">
                  <Sparkline points={series} />
                  <div className="mt-1 text-[10px] text-ink-400">runs · last 14d</div>
                </div>
              )}
            </StatTile>
            <StatTile label="Departments" value={deptTotal} />
            <StatTile
              label="Active certifications"
              value={summary ? summary.active_certs : 0}
              hint={summary ? `of ${summary.issued_certs} issued` : undefined}
              warn={certWarn}
            />
            <StatTile label="API status" value={apiStatus} />
            {system && (
              <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
                <div className="text-sm text-ink-200">System</div>
                <dl className="mt-2 flex flex-col gap-1 text-xs">
                  <Row
                    k="LLM judge"
                    v={system.llm_judge_effective}
                    warn={system.llm_judge_effective === "stub"}
                  />
                  <Row
                    k="Fingerprint"
                    v={system.village_fingerprint}
                    warn={system.village_fingerprint === "drift_detected"}
                  />
                  <Row k="Constitution" v={system.constitution_version ?? "—"} />
                  <Row k="Signing" v={system.hsm_status} warn={system.hsm_status === "stub"} />
                </dl>
              </div>
            )}
          </div>

          {topGaps.length > 0 && (
            <section className="mt-10">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl">Top software gaps</h2>
                <Link href="/dashboard/gaps/software" className="text-sm text-gold-400 hover:underline">
                  View all →
                </Link>
              </div>
              <div className="flex flex-col gap-2">
                {topGaps.map((g) => (
                  <div
                    key={g.ticketId}
                    className="flex items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-sm"
                  >
                    <SeverityPill severity={g.severity} />
                    <span className="font-mono text-xs text-ink-300">{g.forge}</span>
                    <span className="flex-1 text-ink-50">{g.summary}</span>
                    <span className="text-xs text-ink-400">×{g.occurrenceCount}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="mt-10">
            <h2 className="mb-4 text-xl">Agents</h2>
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <th className="px-4 py-3 font-medium">Agent</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Autonomy</th>
                    <th className="px-4 py-3 font-medium">Flags</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {agents.map((a) => (
                    <tr key={a.id} className="hover:bg-ink-800/60">
                      <td className="px-4 py-3">
                        <div className="font-medium text-ink-50">{a.name}</div>
                        <div className="font-mono text-xs text-ink-300">{a.villageAgentId}</div>
                      </td>
                      <td className="px-4 py-3 text-ink-100">{a.role}</td>
                      <td className="px-4 py-3">
                        <AutonomyLadderIndicator level={a.currentAutonomyLevel} />
                      </td>
                      <td className="px-4 py-3">
                        {a.gardnerFlag && (
                          <span className="mr-2 rounded bg-gold-600/20 px-2 py-0.5 text-xs text-gold-300">
                            Gardner
                          </span>
                        )}
                        {a.level10Enabled && (
                          <span className="rounded bg-info/20 px-2 py-0.5 text-xs text-info">
                            L10
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Row({ k, v, warn }: { k: string; v: string; warn?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <dt className="text-ink-400">{k}</dt>
      <dd className={warn ? "text-warning" : "text-ink-100"}>{v}</dd>
    </div>
  );
}
