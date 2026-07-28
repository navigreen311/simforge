import Link from "next/link";

import { AgentsExplorer } from "@/components/agents/AgentsExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  api,
  dashboard,
  type AgentCertRollup,
  type AgentsLegend,
  type AgentSummary,
  type DepartmentSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

const EMPTY_LEGEND: AgentsLegend = { floor: "L1", levels: [], flags: [] };

export default async function AgentsPage() {
  let agents: AgentSummary[] = [];
  let departments: DepartmentSummary[] = [];
  let rollup: AgentCertRollup[] = [];
  let legend: AgentsLegend = EMPTY_LEGEND;
  let total = 0;
  let error: string | null = null;

  try {
    const [agentList, deptList, certRollup, ladder] = await Promise.all([
      api.agents({ page_size: 500 }),
      api.departments(),
      dashboard.agentCerts(),
      api.agentsLegend(),
    ]);
    agents = agentList.items;
    total = agentList.total;
    departments = deptList.items;
    rollup = certRollup.items;
    legend = ladder;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load agents";
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Agents</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/agents/new"
            className="rounded bg-gold-500 px-3 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400"
          >
            + Add agents
          </Link>
          <PageMeta />
        </div>
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        The Village agent roster under certification — autonomy, active certs, and flags. Search,
        filter, and click a row for that agent&apos;s runs.
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
          legend={legend}
        />
      )}
    </div>
  );
}
