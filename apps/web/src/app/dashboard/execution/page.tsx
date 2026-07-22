import { DecisionPill } from "@/components/common/DecisionPill";
import { api, execution, type IntegratedAction, type RunSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

type RunLedger = { run: RunSummary; actions: IntegratedAction[] };

export default async function ExecutionPage() {
  let enabled = false;
  let ledgers: RunLedger[] = [];
  let error: string | null = null;

  try {
    const [status, runList] = await Promise.all([execution.status(), api.runs()]);
    enabled = status.integrated_execution_enabled;
    const integratedRuns = runList.items.filter((r) => r.execution_mode === "integrated");
    ledgers = (
      await Promise.all(
        integratedRuns.map(async (run) => {
          try {
            const { actions } = await execution.runActions(run.run_id);
            return { run, actions };
          } catch {
            return { run, actions: [] as IntegratedAction[] };
          }
        }),
      )
    ).filter((l) => l.actions.length > 0);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load execution data";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Integrated Execution</h1>
      <p className="mb-6 text-ink-200">
        Integrated runs commit agent actions — but every action is PDP-gated, VillageData is never
        written, and the ledger is auditable and reversible (ADR-0025). Off by default.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load execution data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <div
            className={`mb-8 flex items-center gap-3 rounded-xl border p-4 ${
              enabled
                ? "border-warning/40 bg-warning/10"
                : "border-ink-500 bg-ink-800"
            }`}
          >
            <span
              className={`h-3 w-3 rounded-full ${enabled ? "bg-warning" : "bg-ink-300"}`}
              aria-hidden
            />
            <span className="text-sm text-ink-50">
              Integrated execution is{" "}
              <strong className={enabled ? "text-warning" : "text-ink-100"}>
                {enabled ? "ENABLED" : "disabled"}
              </strong>{" "}
              on this deployment.
            </span>
            <span className="ml-auto font-mono text-xs text-ink-400">
              INTEGRATED_EXECUTION_ENABLED={String(enabled)}
            </span>
          </div>

          <h2 className="mb-4 text-xl">Action ledgers</h2>
          {ledgers.length === 0 ? (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
              No integrated-execution runs with committed actions yet. Sandbox runs never write, so
              they don&apos;t appear here.
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {ledgers.map(({ run, actions }) => (
                <div key={run.run_id} className="overflow-hidden rounded-xl border border-ink-500">
                  <div className="flex items-center justify-between bg-ink-800 px-4 py-3">
                    <span className="font-mono text-xs text-ink-100">{run.run_id}</span>
                    <span className="text-xs text-ink-300">{run.scenario_id}</span>
                  </div>
                  <table className="min-w-full text-left text-sm">
                    <thead className="bg-ink-900/40 text-ink-300">
                      <tr>
                        <th className="px-4 py-2 font-medium">Action</th>
                        <th className="px-4 py-2 font-medium">Agent</th>
                        <th className="px-4 py-2 font-medium">PDP decision</th>
                        <th className="px-4 py-2 font-medium">Outcome</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-ink-600">
                      {actions.map((a) => (
                        <tr key={a.action_id} className="hover:bg-ink-800/60">
                          <td className="px-4 py-2 font-mono text-xs text-gold-400">
                            {a.action ?? "—"}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs text-ink-200">
                            {a.agent ?? "—"}
                          </td>
                          <td className="px-4 py-2">
                            {a.decision ? <DecisionPill decision={a.decision} /> : "—"}
                          </td>
                          <td className="px-4 py-2">
                            <span
                              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                a.status === "applied"
                                  ? "bg-success/15 text-success"
                                  : a.status === "reverted"
                                    ? "bg-info/15 text-info"
                                    : "bg-danger/15 text-danger"
                              }`}
                            >
                              {a.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
