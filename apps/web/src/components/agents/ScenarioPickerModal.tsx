"use client";

import { useEffect, useMemo, useState } from "react";

import { api, launchLiveRun, type ScenarioSummary } from "@/lib/api/client";

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};
const TIER_MIN: Record<string, number> = {
  foundational: 1,
  intermediate: 2,
  advanced_crisis: 3,
};
const LEVELS = ["L1", "L2", "L3", "L4", "L5"];

// Launch a scenario run for an agent, opening the live monitor. Prefers scenarios bound to this
// agent; others are allowed but clearly marked with the agent they actually run as. Launching does
// not certify — it's a test.
export function ScenarioPickerModal({
  agentVillageId,
  agentAutonomy,
  onClose,
}: {
  agentVillageId: string;
  agentAutonomy: string;
  onClose: () => void;
}) {
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.scenarios().then((r) => setScenarios(r.items)).catch(() => setScenarios([]));
  }, []);

  const autonomyRank = LEVELS.indexOf(agentAutonomy) + 1 || 1;
  const bound = useMemo(
    () => scenarios.filter((s) => s.testedAgentVillageId === agentVillageId),
    [scenarios, agentVillageId],
  );
  const shown = showAll ? scenarios : bound;

  async function launch(s: ScenarioSummary) {
    if (busy) return;
    setBusy(s.scenarioId);
    setError(null);
    try {
      const res = await launchLiveRun(s.scenarioId);
      window.location.href = `/dashboard/runs/${res.run_id}/watch?agent=${res.agent_village_id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Launch failed");
      setBusy(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-auto rounded-xl border border-ink-500 bg-ink-800 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-lg text-ink-50">Run a scenario for {agentVillageId}</h2>
          <button onClick={onClose} className="text-ink-400 hover:text-ink-200">
            ✕
          </button>
        </div>
        <p className="mb-3 text-xs text-ink-400">
          Launching opens the live monitor. This is a test — it does not certify the agent.
        </p>
        <label className="mb-3 flex items-center gap-2 text-xs text-ink-300">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Show all scenarios (not just this agent&apos;s)
        </label>

        {error && <div className="mb-2 text-xs text-danger">{error}</div>}

        {shown.length === 0 ? (
          <p className="text-sm text-ink-500">
            {bound.length === 0 && !showAll
              ? "No runnable scenarios are bound to this agent. Tick “show all”, or add scenarios to a pack."
              : "No scenarios available."}
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {shown.map((s) => {
              const boundToThis = s.testedAgentVillageId === agentVillageId;
              const tierWarn = boundToThis && autonomyRank < (TIER_MIN[s.tier] ?? 1);
              return (
                <div
                  key={s.scenarioId}
                  className="flex items-center justify-between gap-3 rounded border border-ink-600 p-2"
                >
                  <div className="min-w-0">
                    <div className="text-sm text-ink-100">{s.title}</div>
                    <div className="font-mono text-[10px] text-ink-500">{s.scenarioId}</div>
                    <div className="mt-0.5 flex flex-wrap gap-2 text-[10px]">
                      <span className="rounded bg-ink-600 px-1.5 py-0.5 text-ink-200">
                        {TIER_LABEL[s.tier] ?? s.tier}
                      </span>
                      {!boundToThis && (
                        <span className="text-ink-400">runs as {s.testedAgentVillageId}</span>
                      )}
                      {s.isGolden && <span className="text-gold-400">★ golden</span>}
                      {tierWarn && (
                        <span className="text-warning">
                          ⚠ tier above {agentVillageId}&apos;s {agentAutonomy} — allowed (test)
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => launch(s)}
                    disabled={busy !== null}
                    className="shrink-0 rounded bg-gold-500 px-3 py-1.5 text-xs font-semibold text-ink-900 hover:bg-gold-400 disabled:opacity-40"
                  >
                    {busy === s.scenarioId ? "Launching…" : "▶ Run"}
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
