import { SnapshotCaptureButton } from "@/components/cohort/SnapshotCaptureButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { RefreshButton } from "@/components/ui/RefreshButton";
import { api, cohort, type CohortAnalytics } from "@/lib/api/client";

export const dynamic = "force-dynamic";

// Canonical dimension labels (blueprint §5.2) with a short tooltip.
const DIM: Record<string, { label: string; tip: string }> = {
  c1_breath_coherence: { label: "C1 BREATH Coherence", tip: "Consistency with declared beliefs/values" },
  c2_soul_stability: { label: "C2 SOUL Stability", tip: "Emotional trajectory & proportionality" },
  c3_fot_pressure_management: { label: "C3 FOT Management", tip: "Flow-of-time pressure handling" },
  c5_echo_regret_load: { label: "C5 ECHO Regret Load", tip: "Accumulated regret signal" },
  c6_hfm_drive_balance: { label: "C6 HFM Drive Balance", tip: "Human-fundamental-motive balance" },
  c7_ame_reputation_trajectory: { label: "C7 AME Trajectory", tip: "Reputation / standing trend" },
  cognitive_aggregate: { label: "Aggregate", tip: "Mean of cognitive dimensions" },
};

function cellStyle(v: number | null): React.CSSProperties {
  if (v === null || v === undefined) return { background: "rgba(255,255,255,0.02)" };
  const alpha = 0.12 + 0.5 * Math.max(0, Math.min(1, v));
  return { background: `rgba(212,175,55,${alpha.toFixed(3)})` };
}

function Heatmap({ data }: { data: CohortAnalytics }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-ink-500">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-ink-800 text-ink-200">
          <tr>
            <th className="px-4 py-3 font-medium">Agent</th>
            <th className="px-3 py-3 font-medium">Runs</th>
            {data.dimensions.map((d) => (
              <th key={d} className="px-3 py-3 text-center font-medium" title={DIM[d]?.tip}>
                {DIM[d]?.label ?? d}
              </th>
            ))}
            <th className="px-3 py-3 font-medium">Pctile</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-600">
          {data.agents.map((a) => (
            <tr key={a.agent}>
              <td className="px-4 py-2">
                <div className="font-mono text-xs text-ink-50">{a.agent}</div>
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
                {a.aggregate_percentile === null
                  ? "—"
                  : `${(a.aggregate_percentile * 100).toFixed(0)}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const COG_DIMS = [
  "c1_breath_coherence",
  "c2_soul_stability",
  "c3_fot_pressure_management",
  "c5_echo_regret_load",
  "c6_hfm_drive_balance",
  "c7_ame_reputation_trajectory",
  "cognitive_aggregate",
];

export default async function CohortPage() {
  let analytics: CohortAnalytics[] = [];
  let error: string | null = null;
  try {
    const depts = await api.departments();
    analytics = (
      await Promise.all(
        depts.items.map(async (d) => {
          try {
            return await cohort.analytics(d.villageKey);
          } catch {
            return null;
          }
        }),
      )
    ).filter((a): a is CohortAnalytics => a !== null);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load cohort analytics";
  }

  const hasData = (a: CohortAnalytics) => a.agents.some((ag) => ag.runs > 0);

  // Village-wide mean per dimension across every scored agent.
  const villageAgg: Record<string, number | null> = {};
  for (const d of COG_DIMS) {
    const vals: number[] = [];
    for (const dept of analytics) {
      for (const ag of dept.agents) {
        const v = ag.dims[d];
        if (v !== null && v !== undefined) vals.push(v);
      }
    }
    villageAgg[d] = vals.length ? vals.reduce((s, x) => s + x, 0) / vals.length : null;
  }
  const anyData = analytics.some(hasData);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Cohort Analytics</h1>
        <div className="flex items-center gap-2">
          <SnapshotCaptureButton />
          <RefreshButton />
        </div>
      </div>
      <p className="mb-2 text-ink-200">
        Department-level cognitive drift — each agent&apos;s mean cognitive-dimension scores across
        scored runs, with percentile rank within the cohort (ADR-0034).
      </p>
      <p className="mb-8 text-xs text-ink-400">as of {new Date().toLocaleString()}</p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load cohort analytics: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {anyData && (
            <section>
              <h2 className="mb-3 text-xl">Village-wide average</h2>
              <div className="overflow-x-auto rounded-xl border border-gold-700/40">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      {COG_DIMS.map((d) => (
                        <th key={d} className="px-3 py-3 text-center font-medium" title={DIM[d]?.tip}>
                          {DIM[d]?.label ?? d}
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

          {analytics.map((a) => (
            <section key={a.department}>
              <h2 className="mb-3 text-xl">
                {a.department} <span className="text-sm text-ink-400">· {a.cohort_size} agents</span>
              </h2>
              {hasData(a) ? (
                <Heatmap data={a} />
              ) : (
                <EmptyState
                  title="No scored runs yet"
                  description={`This department will populate as agents are certified and exercised. Currently 0 scored runs across ${a.cohort_size} agent${a.cohort_size === 1 ? "" : "s"}.`}
                  icon="📊"
                />
              )}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
