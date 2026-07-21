import { AutonomyLadderIndicator } from "@/components/agents/AutonomyLadderIndicator";
import { api, type AgentSummary } from "@/lib/api/client";

// Data-heavy read page — always dynamic (blueprint §D.2).
export const dynamic = "force-dynamic";

function StatTile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <div className="text-sm text-ink-200">{label}</div>
      <div className="mt-2 font-display text-3xl text-gold-500">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-300">{hint}</div>}
    </div>
  );
}

export default async function OverviewPage() {
  let agents: AgentSummary[] = [];
  let agentTotal = 0;
  let deptTotal = 0;
  let apiStatus = "error";
  let loadError: string | null = null;

  try {
    const [agentList, deptList, ready] = await Promise.all([
      api.agents({ page_size: 50 }),
      api.departments(),
      api.ready(),
    ]);
    agents = agentList.items;
    agentTotal = agentList.total;
    deptTotal = deptList.total;
    apiStatus = ready.status;
  } catch (e) {
    loadError = e instanceof Error ? e.message : "Failed to reach the API";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Overview</h1>
      <p className="mb-8 text-ink-200">Village certification readiness at a glance.</p>

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
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Agents tracked" value={agentTotal} hint="from Village roster" />
            <StatTile label="Departments" value={deptTotal} />
            <StatTile label="Active certifications" value={0} hint="Phase 7" />
            <StatTile label="API status" value={apiStatus} />
          </div>

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
