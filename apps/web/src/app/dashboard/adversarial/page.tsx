import { AdversarialProbeRunner } from "@/components/adversarial/AdversarialProbeRunner";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  adversarial,
  api,
  health,
  type AgentSummary,
  type PackDetail,
  type PackSummary,
  type ProbeHistoryEntry,
  type ScenarioSummary,
  type Tactic,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

const VERDICT_CLS: Record<string, string> = {
  resisted: "bg-success/15 text-success",
  partial: "bg-warning/15 text-warning",
  capitulated: "bg-danger/15 text-danger",
  no_probes: "bg-ink-600 text-ink-300",
};

export default async function AdversarialPage() {
  let tactics: Tactic[] = [];
  let detection = "substring";
  let scenarios: { scenarioId: string; title: string }[] = [];
  let agents: { villageAgentId: string; name: string }[] = [];
  let history: ProbeHistoryEntry[] = [];
  let agentProvider = "stub";
  let error: string | null = null;

  try {
    const [tacticList, packList, hist, llm, agentList] = await Promise.all([
      adversarial.tactics(),
      api.packs(),
      adversarial.history(),
      health.llmMode(),
      api.agents({ page_size: 100 }),
    ]);
    tactics = tacticList.tactics;
    detection = tacticList.detection;
    history = hist.probes;
    agentProvider = llm.agent_effective;
    agents = agentList.items.map((a: AgentSummary) => ({
      villageAgentId: a.villageAgentId,
      name: a.name,
    }));
    const details = await Promise.all(
      packList.items.map(async (p: PackSummary) => {
        try {
          return await api.pack(p.packId);
        } catch {
          return null;
        }
      }),
    );
    scenarios = details
      .filter((d): d is PackDetail => d !== null)
      .flatMap((d: PackDetail) =>
        d.scenarios.map((s: ScenarioSummary) => ({ scenarioId: s.scenarioId, title: s.title })),
      );
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load adversarial suite";
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Adversarial Suite</h1>
        <PageMeta />
      </div>
      <p className="mb-4 max-w-4xl text-ink-200">
        Red-team probes pressure an agent toward a specific compliance violation and measure whether
        it <strong>resists</strong> or <strong>capitulates</strong> (names a violating action, agrees
        to it, and doesn&apos;t refuse — ADR-0028). This is how SimForge tests whether an agent can be
        talked into breaking compliance.
      </p>
      <div className="mb-6 flex flex-col gap-1 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-ink-100">
        <span>
          ⚠ Probes use the <strong>live LLM provider</strong> (one call per tactic; may incur cost +
          latency). Currently <strong>{agentProvider}</strong>
          {agentProvider === "stub" ? " — free + deterministic." : " — live."}
        </span>
        <span className="text-ink-300">
          Certification impact: capitulation → cert block is <strong>not wired</strong> — probe
          results are <em>advisory only</em>. Detection is <strong>{detection}-match</strong> on the
          agent&apos;s reply (deterministic but brittle — a paraphrased capitulation can slip past).
        </span>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the adversarial suite: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {scenarios.length > 0 && (
            <div className="mb-10">
              <AdversarialProbeRunner
                scenarios={scenarios}
                agents={agents}
                tacticCount={tactics.length}
                agentProvider={agentProvider}
              />
            </div>
          )}

          {/* Probe history */}
          <section className="mb-10">
            <h2 className="mb-3 text-xl">Probe history</h2>
            {history.length === 0 ? (
              <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
                No probes run yet. Run the suite above to record a result here.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">When</th>
                      <th className="px-4 py-2 font-medium">Scenario</th>
                      <th className="px-4 py-2 font-medium">Agent</th>
                      <th className="px-4 py-2 font-medium">Provider</th>
                      <th className="px-4 py-2 text-center font-medium">Fired</th>
                      <th className="px-4 py-2 text-center font-medium">Capitulations</th>
                      <th className="px-4 py-2 font-medium">Verdict</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {history.map((h) => (
                      <tr key={h.id} className="hover:bg-ink-800/60">
                        <td className="px-4 py-2 text-xs text-ink-300">
                          {h.ran_at ? new Date(h.ran_at).toLocaleString() : "—"}
                        </td>
                        <td className="px-4 py-2 text-xs">
                          <div className="text-ink-100">{h.scenario_title || h.scenario_id}</div>
                          <div className="font-mono text-[10px] text-ink-500">{h.scenario_id}</div>
                        </td>
                        <td className="px-4 py-2 font-mono text-xs text-ink-200">{h.agent}</td>
                        <td className="px-4 py-2 text-xs text-ink-300">{h.provider}</td>
                        <td className="px-4 py-2 text-center text-ink-200">{h.probes_run}</td>
                        <td className={`px-4 py-2 text-center ${h.capitulated > 0 ? "text-danger" : "text-ink-200"}`}>
                          {h.capitulated}
                        </td>
                        <td className="px-4 py-2">
                          <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${VERDICT_CLS[h.verdict] ?? "bg-ink-600 text-ink-100"}`}>
                            {h.verdict}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <h2 className="mb-1 text-xl">Tactic catalog</h2>
          <p className="mb-4 text-xs text-ink-400">
            {tactics.length} tactics (data-driven). Each is a pressure toward a specific compliance
            violation.
          </p>
          <div className="grid gap-3 lg:grid-cols-2">
            {tactics.map((t) => (
              <div key={t.id} className="rounded-xl border border-ink-500 bg-ink-800 p-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink-50">{t.name || t.id}</span>
                  <span className="rounded bg-ink-600 px-2 py-0.5 text-[10px] text-ink-100">{t.category}</span>
                  <span className="ml-auto font-mono text-[10px] text-ink-500">{t.id}</span>
                </div>
                <p className="mt-1 text-xs text-ink-300">{t.description}</p>
                <p className="mt-2 border-l-2 border-ink-500 pl-3 text-sm italic text-ink-200">
                  &ldquo;{t.injection}&rdquo;
                </p>
                <div className="mt-2">
                  <span className="text-[10px] text-ink-400">
                    Detection triggers — phrases in the agent&apos;s reply that count as capitulation:
                  </span>
                  <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
                    {t.targets.map((tg) => (
                      <span key={tg} className="rounded bg-danger/10 px-2 py-0.5 font-mono text-[11px] text-danger">
                        {tg}
                      </span>
                    ))}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
