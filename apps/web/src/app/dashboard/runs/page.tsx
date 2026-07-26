import { RunsExplorer } from "@/components/runs/RunsExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  api,
  health,
  type AgentSummary,
  type PackSummary,
  type RunSummary,
  type ScenarioSummary,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

function median(nums: number[]): number | null {
  if (nums.length === 0) return null;
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

export default async function RunsPage({
  searchParams,
}: {
  searchParams: { agent?: string };
}) {
  let agents: AgentSummary[] = [];
  let packs: PackSummary[] = [];
  let scenarios: ScenarioSummary[] = [];
  let allRuns: RunSummary[] = [];
  let stubScores = false;
  let error: string | null = null;
  try {
    const [a, p, s, runs, llm] = await Promise.all([
      api.agents({ page_size: 500 }),
      api.packs(),
      api.scenarios(),
      api.runs({ limit: 500 }),
      health.llmMode().catch(() => null),
    ]);
    agents = a.items;
    packs = p.items;
    scenarios = s.items;
    allRuns = runs.items;
    stubScores = llm?.stub_scores ?? false;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load runs metadata";
  }
  const tierByScenario = Object.fromEntries(scenarios.map((s) => [s.scenarioId, s.tier]));
  const titleByScenario = Object.fromEntries(scenarios.map((s) => [s.scenarioId, s.title]));

  // --- summary computed from the full run history ---
  const total = allRuns.length;
  const distinctScenarios = new Set(allRuns.map((r) => r.scenario_id)).size;
  const distinctAgents = new Set(allRuns.map((r) => r.agent_village_id)).size;
  const passed = allRuns.filter((r) => r.status === "passed").length;
  const blind = allRuns.filter((r) => r.blind_mode).length;
  const passRate = total ? passed / total : 0;
  const med = median(allRuns.map((r) => r.latency_ms ?? 0));

  const pairCounts = new Map<string, number>();
  for (const r of allRuns) {
    const k = `${r.agent_village_id}::${r.scenario_id}`;
    pairCounts.set(k, (pairCounts.get(k) ?? 0) + 1);
  }
  let topPair: { agent: string; scenario: string; n: number } | null = null;
  for (const [k, n] of pairCounts) {
    if (!topPair || n > topPair.n) {
      const [agent, scenario] = k.split("::");
      topPair = { agent, scenario, n };
    }
  }
  const topShare = total && topPair ? topPair.n / total : 0;
  const warn = total > 0 && ((passRate === 1 && stubScores) || topShare >= 0.5);

  return (
    <div className="mx-auto max-w-[90rem]">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Runs</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Scenario executions in plain language — filter by status, tier, agent, pack, mode, and time;
        click a row for the full run.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load runs metadata: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {total > 0 && (
            <div
              className={`mb-6 rounded-xl border p-4 text-sm ${
                warn ? "border-warning/50 bg-warning/10" : "border-ink-500 bg-ink-800"
              }`}
            >
              <div className="flex items-center gap-2">
                {warn && <span className="text-warning">⚠</span>}
                <span className="font-semibold text-ink-50">
                  {total} runs across {distinctScenarios} scenarios and {distinctAgents} agents.
                </span>
              </div>
              {topPair && topShare >= 0.4 && (
                <p className="mt-2 text-ink-100">
                  Most runs ({topPair.n} of {total}) are one agent running one scenario —{" "}
                  <span className="font-mono text-xs">{topPair.agent}</span> on{" "}
                  <span className="font-mono text-xs">{topPair.scenario}</span>. This is a thin test
                  surface — real certification needs varied scenarios across varied agents.
                </p>
              )}
              {passRate === 1 && stubScores && (
                <p className="mt-2 text-warning">
                  All {total} runs passed{med != null ? ` at a median latency of ${med} ms` : ""}{" "}
                  under the stub provider. A 100% pass rate here does not indicate agent quality — it
                  indicates canned scoring. Pass rates become meaningful once the live LLM provider
                  is enabled.
                </p>
              )}
              <div className="mt-2 text-xs text-ink-300">
                {passed}/{total} passed · {blind} blind · {total - blind} not blind
              </div>
            </div>
          )}

          <RunsExplorer
            agents={agents}
            packs={packs}
            tierByScenario={tierByScenario}
            titleByScenario={titleByScenario}
            initialAgent={searchParams.agent}
          />
        </>
      )}
    </div>
  );
}
