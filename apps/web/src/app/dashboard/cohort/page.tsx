import { SnapshotCaptureButton } from "@/components/cohort/SnapshotCaptureButton";
import { api, cohort, type CohortAnalytics } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const SHORT: Record<string, string> = {
  c1_breath_coherence: "C1 Breath",
  c2_soul_stability: "C2 Soul",
  c3_fot_pressure_management: "C3 FoT",
  c5_echo_regret_load: "C5 Echo",
  c6_hfm_drive_balance: "C6 HFM",
  c7_ame_reputation_trajectory: "C7 AME",
  cognitive_aggregate: "Aggregate",
};

// Value 0..1 → a gold-tinted cell; null → muted.
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
              <th key={d} className="px-3 py-3 text-center font-medium">
                {SHORT[d] ?? d}
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
                    <div
                      className="rounded px-2 py-1 text-[11px] text-ink-50"
                      style={cellStyle(v)}
                    >
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
    ).filter((a): a is CohortAnalytics => a !== null && a.agents.length > 0);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load cohort analytics";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Cohort Analytics</h1>
        <SnapshotCaptureButton />
      </div>
      <p className="mb-8 text-ink-200">
        Department-level cognitive drift — each agent&apos;s mean cognitive-dimension scores across its
        scored runs, with percentile rank within the cohort. Surfaces an agent sliding below its peers
        before it fails a run (ADR-0034).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load cohort analytics: <code className="text-danger">{error}</code>
        </div>
      ) : analytics.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No cohort data yet — run some scenarios so agents have cognitive scores.
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {analytics.map((a) => (
            <section key={a.department}>
              <h2 className="mb-3 text-xl">
                {a.department}{" "}
                <span className="text-sm text-ink-400">· {a.cohort_size} agents</span>
              </h2>
              <Heatmap data={a} />
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
