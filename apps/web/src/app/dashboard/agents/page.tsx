import { AgentsExplorer } from "@/components/agents/AgentsExplorer";
import {
  api,
  dashboard,
  type AgentCertRollup,
  type AgentSummary,
  type DepartmentSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  let agents: AgentSummary[] = [];
  let departments: DepartmentSummary[] = [];
  let rollup: AgentCertRollup[] = [];
  let total = 0;
  let error: string | null = null;

  try {
    const [agentList, deptList, certRollup] = await Promise.all([
      api.agents({ page_size: 500 }),
      api.departments(),
      dashboard.agentCerts(),
    ]);
    agents = agentList.items;
    total = agentList.total;
    departments = deptList.items;
    rollup = certRollup.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load agents";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Agents</h1>
      <p className="mb-6 text-ink-200">
        The Village agent roster under certification — autonomy, active certs, and flags. Search,
        filter, and click through to an agent&apos;s runs.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load agents: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <AgentsExplorer
          agents={agents}
          departments={departments}
          rollup={rollup}
          total={total}
        />
      )}
    </div>
  );
}
