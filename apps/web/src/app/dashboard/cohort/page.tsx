import Link from "next/link";

import { SnapshotCaptureButton } from "@/components/cohort/SnapshotCaptureButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";
import { api, cohort, type CohortAnalytics, type SnapshotStatus } from "@/lib/api/client";
import { describeDimension } from "@/lib/dimensions";

export const dynamic = "force-dynamic";

// A percentile within a cohort smaller than this has no meaning (too few peers).
const MIN_COHORT_FOR_PERCENTILE = 3;

// Plain-language cognitive-dimension definitions + direction come from ONE shared source
// (lib/dimensions.ts), reused by Meta-Eval too so the two pages never disagree. Confirmed from the
// scorer source (services/evaluation/dimensions/*) — every numeric cognitive dim is higher-better
// (C5 is stored as 1 − regret, so higher = less regret). C4 ARC is categorical, so it has no column.
const COG_DIM_KEYS = [
  "c1_breath_coherence",
  "c2_soul_stability",
  "c3_fot_pressure_management",
  "c5_echo_regret_load",
  "c6_hfm_drive_balance",
  "c7_ame_reputation_trajectory",
  "cognitive_aggregate",
];
const DIM: Record<string, { label: string; name: string; tip: string }> = Object.fromEntries(
  COG_DIM_KEYS.map((k) => [k, describeDimension(k)]),
);

const COG_DIMS = COG_DIM_KEYS;

function cellStyle(v: number | null): React.CSSProperties {
  if (v === null || v === undefined) return { background: "rgba(255,255,255,0.02)" };
  const alpha = 0.12 + 0.5 * Math.max(0, Math.min(1, v)); // higher = more gold (all dims higher-better)
  return { background: `rgba(212,175,55,${alpha.toFixed(3)})` };
}

function Legend() {
  return (
    <details className="rounded-lg border border-ink-500 bg-ink-800 p-3 text-xs" open>
      <summary className="cursor-pointer font-semibold text-ink-200">
        What the cognitive dimensions mean (all ↑ higher-is-better)
      </summary>
      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
        {COG_DIMS.filter((d) => d !== "cognitive_aggregate").map((d) => (
          <div key={d}>
            <dt className="text-ink-100">
              <span className="font-mono">{DIM[d].label}</span> · {DIM[d].name}{" "}
              <span className="text-success" title="Higher is better">
                ↑
              </span>
            </dt>
            <dd className="text-ink-400">{DIM[d].tip}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-ink-500">
        C4 ARC Narrative Coherence is a categorical value (e.g. “stable” / “sudden_shift”), not a
        0–1 score, so it is not shown as a column here.
      </p>
    </details>
  );
}

function Heatmap({ data }: { data: CohortAnalytics }) {
  const scored = data.agents.filter((a) => a.aggregate_percentile !== null).length;
  const percentileMeaningful = scored >= MIN_COHORT_FOR_PERCENTILE;
  return (
    <div className="overflow-x-auto rounded-xl border border-ink-500">
      <table className="min-w-full text-left text-sm">
        <thead className="sticky top-0 bg-ink-800 text-ink-200">
          <tr>
            <th className="px-4 py-3 font-medium">Agent</th>
            <th className="px-3 py-3 font-medium">Runs</th>
            {data.dimensions.map((d) => (
              <th key={d} className="px-3 py-3 text-center font-medium" title={DIM[d]?.tip}>
                {DIM[d]?.label ?? d} <span className="text-success">↑</span>
              </th>
            ))}
            <th className="px-3 py-3 font-medium">Percentile</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-600">
          {data.agents.map((a) => (
            <tr key={a.agent}>
              <td className="px-4 py-2">
                <Link
                  href={`/dashboard/runs?agent=${a.agent}`}
                  className="font-mono text-xs text-gold-400 hover:underline"
                >
                  {a.agent}
                </Link>
                <div className="text-[10px] text-ink-400">{a.role}</div>
              </td>
              <td className="px-3 py-2 text-ink-300">{a.runs}</td>
              {data.dimensions.map((d) => {
                const v = a.dims[d];
                return (
                  <td key={d} className="px-1 py-1 text-center">
                    <div className="rounded px-2 py-1 text-[11px] text-ink-50" style={cellStyle(v)}>
                      {v === null || v === undefined ? "—" : v.toFixed(2)}
                    </div>
                  </td>
                );
              })}
              <td className="px-3 py-2 text-ink-100">
                {a.aggregate_percentile === null ? (
                  "—"
                ) : percentileMeaningful ? (
                  `${(a.aggregate_percentile * 100).toFixed(0)}%`
                ) : (
                  <span
                    className="cursor-help text-xs italic text-ink-500"
                    title={`Percentile ranks compare an agent to others in its department. With only ${scored} scored agent${scored === 1 ? "" : "s"} here, a percentile isn't meaningful.`}
                  >
                    n/a · {scored} in cohort
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function CohortPage() {
  let analytics: CohortAnalytics[] = [];
  let snap: SnapshotStatus | null = null;
  let error: string | null = null;
  try {
    const depts = await api.departments();
    [analytics, snap] = await Promise.all([
      Promise.all(
        depts.items.map((d) => cohort.analytics(d.villageKey).catch(() => null)),
      ).then((xs) => xs.filter((a): a is CohortAnalytics => a !== null)),
      cohort.snapshotStatus().catch(() => null),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load cohort analytics";
  }

  const hasData = (a: CohortAnalytics) => a.agents.some((ag) => ag.runs > 0);

  // Real coverage + a thin Village-wide mean per dimension across every scored agent.
  const totalAgents = analytics.reduce((s, a) => s + a.cohort_size, 0);
  const scoredAgents = new Set<string>();
  let totalScoredRuns = 0;
  const villageAgg: Record<string, number | null> = {};
  for (const d of COG_DIMS) {
    const vals: number[] = [];
    for (const dept of analytics)
      for (const ag of dept.agents) {
        if (ag.runs > 0) {
          scoredAgents.add(ag.agent);
        }
        const v = ag.dims[d];
        if (v !== null && v !== undefined) vals.push(v);
      }
    villageAgg[d] = vals.length ? vals.reduce((s, x) => s + x, 0) / vals.length : null;
  }
  for (const dept of analytics) for (const ag of dept.agents) totalScoredRuns += ag.runs;
  const withData = analytics.filter(hasData);
  const empty = analytics.filter((a) => !hasData(a));
  const anyData = withData.length > 0;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Cohort Analytics</h1>
        <div className="flex items-center gap-2">
          <SnapshotCaptureButton />
          <RefreshButton />
        </div>
      </div>
      <p className="mb-2 max-w-prose text-ink-200">
        Department-level cognitive drift — each agent&apos;s mean cognitive-dimension scores across
        scored runs, with a percentile rank within its department cohort (ADR-0034).
      </p>
      <p className="mb-6 text-xs text-ink-400">as of {new Date().toLocaleString()}</p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load cohort analytics: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {/* Coverage + honesty */}
          <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm">
            <p className="text-ink-100">
              <strong>{scoredAgents.size}</strong> of {totalAgents} agents have scored runs.{" "}
              <strong>{empty.length}</strong> of {analytics.length} departments have no scored runs
              yet.
            </p>
            <p className="mt-1 text-xs text-ink-300">
              The Village-wide average below is computed from {scoredAgents.size} scored agent
              {scoredAgents.size === 1 ? "" : "s"} across {totalScoredRuns} run
              {totalScoredRuns === 1 ? "" : "s"} — it is not yet representative of the full roster.
              Scores include stub-provider heuristics (P7/C1/C2 are LLM-judge dims, deterministic
              under the stub), so treat them as indicative, not settled.
            </p>
          </div>

          {/* Drift status — honest about snapshots */}
          <div className="rounded-lg border border-ink-500 bg-ink-800 p-3 text-xs">
            <span className="font-semibold text-ink-200">Drift: </span>
            {snap === null ? (
              <span className="text-ink-400">snapshot status unavailable.</span>
            ) : snap.drift_available ? (
              <span className="text-ink-200">
                {snap.snapshot_dates} snapshot dates captured (latest {snap.latest_date}). Per-agent
                drift is available via each agent&apos;s cognitive history.
              </span>
            ) : (
              <span className="text-ink-300">
                {snap.total_snapshots > 0
                  ? `Snapshots exist for a single date${snap.latest_date ? ` (${snap.latest_date})` : ""}, so no drift is available yet — drift compares snapshots across dates.`
                  : "No historical snapshots captured yet — drift will appear once daily snapshots accumulate."}{" "}
                Use “Capture snapshots” above (it records today&apos;s cognitive state for every
                agent) and capture again on a later day to see drift.
              </span>
            )}
          </div>

          <Legend />

          {anyData && (
            <section>
              <h2 className="mb-3 text-xl">
                Village-wide average{" "}
                <span className="text-sm font-normal text-ink-400">
                  · thin sample ({scoredAgents.size} agent{scoredAgents.size === 1 ? "" : "s"})
                </span>
              </h2>
              <div className="overflow-x-auto rounded-xl border border-gold-700/40">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      {COG_DIMS.map((d) => (
                        <th key={d} className="px-3 py-3 text-center font-medium" title={DIM[d]?.tip}>
                          {DIM[d]?.label ?? d} <span className="text-success">↑</span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      {COG_DIMS.map((d) => (
                        <td key={d} className="px-3 py-3 text-center text-ink-50">
                          {villageAgg[d] === null ? "—" : villageAgg[d]!.toFixed(2)}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* Departments with data first */}
          {withData.map((a) => (
            <section key={a.department}>
              <h2 className="mb-3 text-xl">
                {a.department}{" "}
                <span className="text-sm text-ink-400">· {a.cohort_size} agents</span>
              </h2>
              <Heatmap data={a} />
            </section>
          ))}

          {/* Empty departments collapsed so they don't bury the real data */}
          {empty.length > 0 && (
            <details className="rounded-xl border border-ink-500 bg-ink-800/40 p-4">
              <summary className="cursor-pointer text-sm text-ink-300">
                {empty.length} department{empty.length === 1 ? "" : "s"} with no scored runs yet —
                expand
              </summary>
              <div className="mt-3 flex flex-col gap-3">
                {empty.map((a) => (
                  <EmptyState
                    key={a.department}
                    title={a.department}
                    description={`No scored runs yet — ${a.cohort_size} agent${a.cohort_size === 1 ? "" : "s"}, 0 scored. Will populate as agents are certified and exercised.`}
                    icon="📊"
                  />
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
