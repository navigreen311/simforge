"use client";

import { useState } from "react";

import { probeScenario, type AdversarialReport } from "@/lib/api/client";

type ScenarioOption = { scenarioId: string; title: string };

export function AdversarialProbeRunner({ scenarios }: { scenarios: ScenarioOption[] }) {
  const [scenarioId, setScenarioId] = useState(scenarios[0]?.scenarioId ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<AdversarialReport | null>(null);

  async function onRun() {
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await probeScenario(scenarioId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Probe failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <h2 className="mb-1 text-xl">Run a red-team probe</h2>
      <p className="mb-4 text-sm text-ink-300">
        Fires every tactic at the scenario&apos;s tested agent and scores resistance. Uses the live
        LLM provider — may take a moment.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-1 flex-col gap-1 text-xs text-ink-200">
          Scenario
          <select
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            className="min-w-[18rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 text-sm text-ink-50"
          >
            {scenarios.map((s) => (
              <option key={s.scenarioId} value={s.scenarioId}>
                {s.title} ({s.scenarioId})
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={onRun}
          disabled={busy || !scenarioId}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
        >
          {busy ? "Probing…" : "Probe"}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}

      {report && (
        <div className="mt-5">
          <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
            <span className="font-mono text-xs text-ink-300">{report.agent}</span>
            <span
              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                report.capitulated === 0
                  ? "bg-success/15 text-success"
                  : "bg-danger/15 text-danger"
              }`}
            >
              {report.resisted}/{report.probes_run} resisted
            </span>
            <span className="text-ink-300">
              resistance {(report.resistance_rate * 100).toFixed(0)}%
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {report.results.map((r) => (
              <div
                key={r.tactic}
                className="rounded-lg border border-ink-600 bg-ink-900/50 px-4 py-3 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      r.resisted ? "bg-success" : "bg-danger"
                    }`}
                    aria-hidden
                  />
                  <span className="font-mono text-xs text-gold-400">{r.tactic}</span>
                  <span className="rounded bg-ink-700 px-2 py-0.5 text-[11px] text-ink-200">
                    {r.category}
                  </span>
                  <span className="ml-auto text-xs text-ink-300">
                    {r.resisted ? "resisted" : `capitulated${r.matched_marker ? ` · ${r.matched_marker}` : ""}`}
                  </span>
                </div>
                <p className="mt-2 line-clamp-3 font-mono text-[11px] text-ink-400">
                  {r.response_excerpt}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
