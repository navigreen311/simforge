import { RunsExplorer } from "@/components/runs/RunsExplorer";
import { api, type AgentSummary, type PackSummary, type ScenarioSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function RunsPage({
  searchParams,
}: {
  searchParams: { agent?: string };
}) {
  let agents: AgentSummary[] = [];
  let packs: PackSummary[] = [];
  let scenarios: ScenarioSummary[] = [];
  let error: string | null = null;
  try {
    const [a, p, s] = await Promise.all([
      api.agents({ page_size: 500 }),
      api.packs(),
      api.scenarios(),
    ]);
    agents = a.items;
    packs = p.items;
    scenarios = s.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load runs metadata";
  }
  const tierByScenario = Object.fromEntries(scenarios.map((s) => [s.scenarioId, s.tier]));

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Runs</h1>
      <p className="mb-6 text-ink-200">
        Scenario executions — filter by status, tier, agent, pack, mode, and time; click a row for
        the full run.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load runs metadata: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <RunsExplorer
          agents={agents}
          packs={packs}
          tierByScenario={tierByScenario}
          initialAgent={searchParams.agent}
        />
      )}
    </div>
  );
}
