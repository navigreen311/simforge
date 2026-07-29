"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { probeScenario, type AdversarialReport } from "@/lib/api/client";

type ScenarioOption = { scenarioId: string; title: string };
type AgentOption = { villageAgentId: string; name: string };

const VERDICT: Record<string, { label: string; cls: string; meaning: (r: AdversarialReport) => string }> = {
  resisted: {
    label: "RESISTED",
    cls: "border-success/40 bg-success/10 text-success",
    meaning: () => "The agent refused every tactic — it did not agree to any violating action.",
  },
  capitulated: {
    label: "CAPITULATED",
    cls: "border-danger/50 bg-danger/15 text-danger",
    meaning: (r) =>
      `The agent gave in to ${r.capitulated} of ${r.probes_run} tactics — it named/agreed to a violating action without refusing.`,
  },
  partial: {
    label: "PARTIAL",
    cls: "border-warning/50 bg-warning/15 text-warning",
    meaning: (r) => `The agent resisted some tactics but capitulated on ${r.capitulated}.`,
  },
  no_probes: {
    label: "INDETERMINATE",
    cls: "border-warning/50 bg-warning/15 text-warning",
    meaning: () => "0 tactics fired — nothing to judge.",
  },
};

export function AdversarialProbeRunner({
  scenarios,
  agents,
  tacticCount,
  agentProvider,
}: {
  scenarios: ScenarioOption[];
  agents: AgentOption[];
  tacticCount: number;
  agentProvider: string;
}) {
  const router = useRouter();
  const [scenarioId, setScenarioId] = useState(scenarios[0]?.scenarioId ?? "");
  const [agentId, setAgentId] = useState(""); // "" = the scenario's bound agent
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<AdversarialReport | null>(null);

  const isLive = agentProvider !== "stub";

  async function fire() {
    setConfirming(false);
    setBusy(true);
    setError(null);
    setReport(null);
    try {
      setReport(await probeScenario(scenarioId, agentId || undefined));
      router.refresh(); // refresh the persisted history table below
    } catch (e) {
      setError(e instanceof Error ? e.message : "Probe failed");
    } finally {
      setBusy(false);
    }
  }

  function onRun() {
    if (isLive) setConfirming(true);
    else void fire();
  }

  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <h2 className="mb-1 text-xl">Run the full tactic suite</h2>
      <p className="mb-4 text-sm text-ink-300">
        Fires all {tacticCount} tactics at the selected agent and scores resistance. Provider:{" "}
        <strong className={isLive ? "text-warning" : "text-ink-100"}>{agentProvider}</strong>
        {isLive ? " (live — cost + latency)" : " (free + deterministic)"}.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-1 flex-col gap-1 text-xs text-ink-200">
          Scenario
          <select
            value={scenarioId}
            onChange={(e) => setScenarioId(e.target.value)}
            className="min-w-[16rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 text-sm text-ink-50"
          >
            {scenarios.map((s) => (
              <option key={s.scenarioId} value={s.scenarioId}>
                {s.title} ({s.scenarioId})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs text-ink-200">
          Agent
          <select
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            className="min-w-[14rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 text-sm text-ink-50"
          >
            <option value="">Scenario&apos;s bound agent</option>
            {agents.map((a) => (
              <option key={a.villageAgentId} value={a.villageAgentId}>
                {a.name} ({a.villageAgentId})
              </option>
            ))}
          </select>
        </label>
        <button
          onClick={onRun}
          disabled={busy || !scenarioId}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
        >
          {busy ? "Probing…" : "Run full suite"}
        </button>
      </div>

      {busy && (
        <p className="mt-3 text-xs text-ink-300">
          Firing {tacticCount} tactics at the agent and checking each response for capitulation…
        </p>
      )}

      {confirming && (
        <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-ink-100">
          <p>
            This will make <strong>{tacticCount}</strong> live LLM calls (≈1 per tactic) via{" "}
            <strong>{agentProvider}</strong> — may incur cost + latency.
          </p>
          <div className="mt-2 flex gap-2">
            <button onClick={fire} className="rounded bg-gold-500 px-3 py-1 text-xs font-semibold text-ink-900 hover:bg-gold-400">
              Confirm — run {tacticCount} calls
            </button>
            <button onClick={() => setConfirming(false)} className="rounded border border-ink-500 px-3 py-1 text-xs text-ink-200 hover:bg-ink-700">
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="mt-3 rounded border border-danger/40 bg-danger/10 p-2 text-sm text-danger">
          Probe failed: {error}
        </p>
      )}

      {report && <ResultPanel report={report} />}
    </div>
  );
}

function ResultPanel({ report }: { report: AdversarialReport }) {
  const v = VERDICT[report.verdict] ?? VERDICT.no_probes;
  return (
    <div className="mt-5 flex flex-col gap-3">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-300">
        <span className="text-ink-100">{report.scenario_title}</span>
        <span className="font-mono text-[10px] text-ink-500">{report.scenario_id}</span>
        <span>· agent <span className="text-ink-100">{report.agent_name}</span> <span className="font-mono text-[10px] text-ink-500">{report.agent}</span></span>
        <span>· provider <span className="text-ink-100">{report.provider}</span></span>
        <span>· just now</span>
        <span>· {report.probes_run} tactics fired</span>
      </div>

      {/* Overall verdict */}
      <div className={`rounded-xl border p-3 text-sm ${v.cls}`}>
        <span className="font-semibold uppercase">{v.label}</span>{" "}
        <span className="text-ink-50">{v.meaning(report)}</span>
      </div>

      {/* Per-tactic breakdown */}
      <div className="flex flex-col gap-2">
        {report.results.map((r) => (
          <div key={r.tactic} className="rounded-lg border border-ink-600 bg-ink-900/50 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className={`h-2.5 w-2.5 rounded-full ${r.resisted ? "bg-success" : "bg-danger"}`} aria-hidden />
              <span className="text-ink-50">{r.name}</span>
              <span className="rounded bg-ink-700 px-2 py-0.5 text-[10px] text-ink-300">{r.category}</span>
              <span className={`ml-auto text-xs font-semibold ${r.resisted ? "text-success" : "text-danger"}`}>
                {r.resisted ? "resisted" : "capitulated"}
              </span>
            </div>
            <p className="mt-2 border-l-2 border-ink-600 pl-3 text-xs italic text-ink-300">
              Asked: &ldquo;{r.injection}&rdquo;
            </p>
            <p className="mt-1 text-[11px] text-ink-400">
              Response: <span className="font-mono">{r.response_excerpt || "—"}</span>
            </p>
            {!r.resisted && r.matched_marker && (
              <p className="mt-1 text-[11px] text-danger">
                Detected capitulation: the reply contained &ldquo;{r.matched_marker}&rdquo; with an
                agreement and no refusal.
              </p>
            )}
          </div>
        ))}
      </div>

      <p className="text-[11px] text-ink-400">
        This result is advisory — it does not currently block or revoke certification.
      </p>
    </div>
  );
}
