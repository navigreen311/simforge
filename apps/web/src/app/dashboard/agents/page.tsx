import { AutonomyLadderIndicator } from "@/components/agents/AutonomyLadderIndicator";
import { api, type AgentSummary, type DepartmentSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  let agents: AgentSummary[] = [];
  let departments: DepartmentSummary[] = [];
  let error: string | null = null;

  try {
    const [agentList, deptList] = await Promise.all([
      api.agents({ page_size: 200 }),
      api.departments(),
    ]);
    agents = agentList.items;
    departments = deptList.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load agents";
  }
  const deptById = new Map(departments.map((d) => [d.id, d.name]));

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Agents</h1>
      <p className="mb-8 text-ink-200">
        The Village agent roster under certification, with current autonomy level and flags.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load agents: <code className="text-danger">{error}</code>
        </div>
      ) : agents.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No agents in the roster.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Agent</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Department</th>
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
                  <td className="px-4 py-3 text-ink-200">
                    {deptById.get(a.departmentId) ?? a.departmentId}
                  </td>
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
                      <span className="rounded bg-info/20 px-2 py-0.5 text-xs text-info">L10</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
