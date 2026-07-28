"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { runLive, type LiveRunView, type LiveTraceEvent } from "@/lib/api/client";

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};
const STATUS_STYLE: Record<string, string> = {
  queued: "bg-ink-600 text-ink-200",
  running: "bg-info/20 text-info",
  scoring: "bg-gold-600/20 text-gold-300",
  passed: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  errored: "bg-danger/20 text-danger",
};

// Map a raw trace event to a labeled, typed activity entry. Shows only what the executor emitted —
// a gap in the trace is left as-is, never filled in.
function entryOf(e: LiveTraceEvent): { label: string; tone: string; text: string; meta?: string } {
  const p = e.payload || {};
  const s = (k: string) => (typeof p[k] === "string" ? (p[k] as string) : "");
  if (p.forge) {
    const cap = s("cap") || s("module");
    const result = p.result !== undefined ? ` → ${JSON.stringify(p.result)}` : "";
    return { label: "Tool call", tone: "tool", text: `${p.forge}${cap ? `.${cap}` : ""}${result}` };
  }
  switch (e.event_type) {
    case "agent_response":
      return {
        label: "Agent turn",
        tone: "agent",
        text: s("content"),
        meta: typeof p.tokens === "number" ? `${p.tokens} tok` : undefined,
      };
    case "cold_open":
      return { label: "Scenario", tone: "scenario", text: s("content") };
    case "turn_start":
      return { label: "System", tone: "muted", text: `Turn ${p.turn ?? "?"} begins` };
    case "resolution":
      return { label: "System", tone: "outcome", text: `Resolved: ${s("outcome") || "—"}` };
    case "wrap":
      return { label: "System", tone: "muted", text: "Run wrapped" };
    case "setup":
      return { label: "System", tone: "muted", text: "Setup" };
    default:
      if (e.event_type.includes("adversarial"))
        return { label: "Adversarial probe", tone: "warning", text: JSON.stringify(p) };
      return { label: e.event_type, tone: "muted", text: JSON.stringify(p) };
  }
}

const TONE: Record<string, string> = {
  agent: "border-info/40 bg-info/5",
  scenario: "border-ink-500 bg-ink-800",
  tool: "border-gold-600/40 bg-gold-600/5",
  outcome: "border-success/30 bg-success/5",
  warning: "border-warning/40 bg-warning/5",
  muted: "border-ink-600 bg-ink-900",
};
const LABEL_TONE: Record<string, string> = {
  "Agent turn": "text-info",
  Scenario: "text-ink-300",
  "Tool call": "text-gold-300",
  System: "text-ink-500",
  "Adversarial probe": "text-warning",
};

export function LiveRunMonitor({ runId, backHref }: { runId: string; backHref?: string }) {
  const [view, setView] = useState<LiveRunView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [degraded, setDegraded] = useState(false);
  const [everRunning, setEverRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      if (!active) return;
      try {
        const v = await runLive(runId);
        failures = 0;
        setDegraded(false);
        setView(v);
        if (["queued", "running", "scoring"].includes(v.status)) setEverRunning(true);
        if (v.done) return; // terminal — stop polling
      } catch {
        failures += 1;
        setDegraded(failures >= 2);
        if (failures > 30) {
          setError("Lost connection to the run stream.");
          return;
        }
      }
      timer = setTimeout(tick, 1500);
    }
    timer = setTimeout(tick, 0);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [runId]);

  // Auto-scroll the activity feed on new entries, unless the operator is hovering (paused).
  useEffect(() => {
    if (!paused && feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [view?.trace.length, paused]);

  if (error)
    return (
      <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
        {error}{" "}
        <button onClick={() => window.location.reload()} className="underline">
          retry
        </button>
      </div>
    );
  if (!view) return <p className="text-sm text-ink-400">Connecting to run…</p>;

  const instant = view.done && !everRunning && (view.elapsed_ms ?? 0) < 1500;
  const entries = view.trace.map(entryOf).filter((x) => x.text || x.label !== "System");

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="rounded-xl border border-ink-500 bg-ink-800 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="text-lg text-gold-500">{view.scenario_title}</div>
            <div className="font-mono text-xs text-ink-400">{view.scenario_id}</div>
          </div>
          <span className={`rounded px-2 py-0.5 text-sm font-semibold ${STATUS_STYLE[view.status]}`}>
            {view.status}
          </span>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <Chip label={`agent: ${view.agent_name}`} />
          <Chip label={`tier: ${TIER_LABEL[view.tier] ?? view.tier}`} />
          <Chip
            label={view.execution_mode}
            tone={view.integrated ? "danger" : "neutral"}
            title={
              view.integrated
                ? "Integrated mode — touches real, write-enabled Forge systems."
                : "Sandbox — mock Forge APIs, no real systems touched."
            }
          />
          <Chip label={`${(view.elapsed_ms / 1000).toFixed(1)}s`} />
          {view.current_phase && <Chip label={`phase: ${view.current_phase}`} />}
          <Chip label={`turn ${view.current_turn}`} />
          {view.tokens_used != null && <Chip label={`${view.tokens_used} tok`} />}
        </div>
        {view.integrated && view.forges_called.length > 0 && (
          <div className="mt-2 text-xs text-danger">
            Real Forges called: {view.forges_called.join(", ")}
          </div>
        )}
      </div>

      {instant && (
        <div className="rounded-lg border border-info/40 bg-info/10 p-3 text-xs text-info">
          This run completed instantly under the stub provider. Live step-by-step streaming becomes
          meaningful once the live LLM provider is enabled and runs take real time — the full
          transcript and score are shown below.
        </div>
      )}
      {degraded && !view.done && (
        <div className="rounded border border-warning/40 bg-warning/10 p-2 text-xs text-warning">
          Stream degraded — retrying. Showing the last known state.
        </div>
      )}
      {!instant && !view.done && (
        <div className="text-xs text-ink-500">
          Watching live · a live run consumes LLM-provider calls (a real cost when not stubbed).
        </div>
      )}

      {/* Activity transcript */}
      <div>
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-semibold text-ink-200">Agent activity</span>
          {!view.done && <span className="text-ink-500">{paused ? "paused (hover)" : "live"}</span>}
        </div>
        <div
          ref={feedRef}
          onMouseEnter={() => setPaused(true)}
          onMouseLeave={() => setPaused(false)}
          className="flex max-h-[420px] flex-col gap-2 overflow-auto rounded-lg border border-ink-500 bg-ink-900 p-3"
        >
          {entries.length === 0 ? (
            <p className="text-xs text-ink-500">Waiting for the first step…</p>
          ) : (
            entries.map((x, i) => (
              <div key={i} className={`rounded border p-2 text-xs ${TONE[x.tone] ?? TONE.muted}`}>
                <div className="mb-0.5 flex items-center gap-2">
                  <span className={`font-semibold ${LABEL_TONE[x.label] ?? "text-ink-400"}`}>
                    {x.label}
                  </span>
                  {x.meta && <span className="text-ink-500">{x.meta}</span>}
                </div>
                <div className="whitespace-pre-wrap text-ink-100">{x.text || "—"}</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Live scoring */}
      <Scoring view={view} />

      {/* Completion */}
      {view.done && (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`rounded px-2 py-0.5 font-semibold ${STATUS_STYLE[view.status]}`}>
              {view.status}
            </span>
            <span className="text-ink-300">outcome: {view.outcome ?? "—"}</span>
            <span className="text-ink-300">latency: {view.latency_ms ?? "—"}ms</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-3 text-xs">
            <Link href={`/dashboard/runs/${view.run_id}`} className="text-gold-400 hover:underline">
              Open persisted run →
            </Link>
            <Link
              href={`/dashboard/lineage?root=urn:gc:village:run:${view.run_id}`}
              className="text-gold-400 hover:underline"
            >
              View Lineage →
            </Link>
            {backHref && (
              <Link href={backHref} className="text-ink-300 hover:underline">
                ← Back to agent
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Chip({ label, tone, title }: { label: string; tone?: string; title?: string }) {
  const cls = tone === "danger" ? "bg-danger/15 text-danger" : "bg-ink-600 text-ink-200";
  return (
    <span className={`rounded px-2 py-0.5 ${cls} ${title ? "cursor-help" : ""}`} title={title}>
      {label}
    </span>
  );
}

const DIMS: [keyof NonNullable<LiveRunView["scorecard"]>, string][] = [
  ["p1_correctness", "Correctness"],
  ["p2_compliance", "Compliance"],
  ["p3_process_fidelity", "Process"],
  ["p4_time_to_resolution", "Time"],
  ["p5_escalation", "Escalation"],
  ["p6_doc_quality", "Docs"],
  ["p7_customer_experience", "CX (judge)"],
  ["p8_cost_discipline", "Cost"],
  ["c1_breath_coherence", "Breath (judge)"],
  ["c2_soul_stability", "Soul (judge)"],
  ["c3_fot_pressure_management", "Pressure"],
  ["c5_echo_regret_load", "Regret"],
  ["c6_hfm_drive_balance", "Drive"],
  ["c7_ame_reputation_trajectory", "Reputation"],
];

function Scoring({ view }: { view: LiveRunView }) {
  if (view.status === "scoring")
    return (
      <div className="rounded-lg border border-gold-600/30 bg-gold-600/5 p-3 text-xs text-gold-300">
        Scoring — computing the 15-dimension rubric…
      </div>
    );
  const card = view.scorecard;
  if (!card) return null;
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="font-semibold text-ink-200">Scorecard</span>
        <span
          className={`rounded px-2 py-0.5 ${card.readiness_gate_passed ? "bg-success/15 text-success" : "bg-danger/15 text-danger"}`}
        >
          gate {card.readiness_gate_passed ? "passed" : "failed"}
        </span>
        {card.auto_fail_reason && (
          <span className="text-danger">auto-fail: {card.auto_fail_reason}</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-1 text-xs sm:grid-cols-4">
        {DIMS.map(([k, label]) => {
          const v = card[k] as number | null; // DIMS keys are all numeric dimensions
          return (
            <div key={k} className="flex justify-between rounded bg-ink-900 px-2 py-1">
              <span className="text-ink-400">{label}</span>
              <span className="font-mono text-ink-100">{v == null ? "—" : v.toFixed(2)}</span>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[10px] text-ink-500">
        “judge” dimensions (P7/C1/C2) use the LLM judge — deterministic heuristics under the stub
        provider, real signal only with a live judge.
      </p>
    </div>
  );
}
