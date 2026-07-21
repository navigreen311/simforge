import Link from "next/link";
import { notFound } from "next/navigation";

import { FifteenDimChart } from "@/components/runs/FifteenDimChart";
import { RunStatusBadge } from "@/components/runs/RunStatusBadge";
import { api, type Scorecard, type RunSummary, type TranscriptTurn } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const ROLE_STYLES: Record<string, string> = {
  scenario: "border-ink-500 bg-ink-800",
  agent: "border-gold-700 bg-gold-900/20",
  world: "border-info/40 bg-info/5",
};

function TranscriptBubble({ turn }: { turn: TranscriptTurn }) {
  const isComplication = turn.content.startsWith("[COMPLICATION]");
  return (
    <div
      className={`rounded-lg border p-3 ${
        isComplication ? "border-danger/50 bg-danger/10" : ROLE_STYLES[turn.role] ?? "border-ink-500"
      }`}
    >
      <div className="mb-1 text-[10px] uppercase tracking-wide text-ink-300">{turn.role}</div>
      <div className="text-sm text-ink-50">{turn.content}</div>
    </div>
  );
}

export default async function RunDetailPage({ params }: { params: { runId: string } }) {
  let run: RunSummary;
  let turns: TranscriptTurn[] = [];
  let events: { timestamp: string; event_type: string; phase: string; turn_number: number | null }[] =
    [];
  try {
    [run, { turns }, { events }] = await Promise.all([
      api.run(params.runId),
      api.transcript(params.runId),
      api.trace(params.runId),
    ]);
  } catch {
    notFound();
  }

  // Scorecard is best-effort (absent for errored runs).
  let scorecard: Scorecard | null = null;
  try {
    scorecard = await api.scorecard(params.runId);
  } catch {
    scorecard = null;
  }

  return (
    <div className="mx-auto max-w-5xl">
      <Link href="/dashboard/runs" className="text-sm text-ink-300 hover:text-ink-100">
        ← Runs
      </Link>
      <div className="mt-2 flex items-center justify-between">
        <h1 className="text-2xl">
          <span className="font-mono text-gold-400">{run.scenario_id}</span>
        </h1>
        <RunStatusBadge status={run.status} />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Stat label="Agent" value={run.agent_village_id} mono />
        <Stat label="Outcome" value={run.outcome ?? "—"} />
        <Stat label="Latency" value={run.latency_ms != null ? `${run.latency_ms}ms` : "—"} />
        <Stat label="Tokens" value={run.tokens_used != null ? String(run.tokens_used) : "—"} />
      </div>

      {scorecard && (
        <section className="mt-8">
          <FifteenDimChart card={scorecard} />
        </section>
      )}

      <section className="mt-8 grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-lg">Transcript</h2>
          <div className="flex flex-col gap-3">
            {turns.map((t, i) => (
              <TranscriptBubble key={i} turn={t} />
            ))}
          </div>
        </div>
        <div>
          <h2 className="mb-3 text-lg">Trace</h2>
          <ol className="flex flex-col gap-1 text-xs">
            {events.map((e, i) => (
              <li key={i} className="flex items-center justify-between rounded bg-ink-800 px-2 py-1">
                <span className="text-ink-100">{e.event_type}</span>
                <span className="font-mono text-ink-400">{e.phase}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border border-ink-500 bg-ink-800 p-3">
      <div className="text-xs text-ink-300">{label}</div>
      <div className={`mt-1 text-ink-50 ${mono ? "font-mono text-xs" : ""}`}>{value}</div>
    </div>
  );
}
