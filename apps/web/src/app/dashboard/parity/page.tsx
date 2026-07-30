import { PageMeta } from "@/components/ui/PageMeta";
import { parity, type ParitySummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ParityPage() {
  let data: ParitySummary | null = null;
  let error: string | null = null;
  try {
    data = await parity.summary();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load parity data";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Forge Parity SLA</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        A certification is only as trustworthy as the sandbox it ran in. This tracks how closely each
        Forge&apos;s sandbox matches production behaviour. A forge measured below the SLA is{" "}
        <code>unsafe_to_certify</code>. Measuring real parity needs production telemetry, so parity is
        recorded explicitly — a forge with no measurement reads as safe rather than fabricating a
        score (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load parity data: <code className="text-danger">{error}</code>
        </div>
      ) : data ? (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-xl border border-ink-500 bg-ink-800 p-4 text-sm">
            <span className="text-ink-200">
              SLA threshold:{" "}
              <span className="font-mono text-gold-400">{data.sla_threshold.toFixed(2)}</span>
            </span>
            <span className="text-ink-200">
              Enforcement:{" "}
              {data.enforced ? (
                <span className="font-semibold text-danger">ON — sub-SLA forges block issuance</span>
              ) : (
                <span className="text-ink-300">off (annotate-only; set PARITY_ENFORCE to block)</span>
              )}
            </span>
          </div>

          {data.forges.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <th className="px-4 py-2 font-medium">Forge capability</th>
                    <th className="px-3 py-2 text-center font-medium">Parity</th>
                    <th className="px-3 py-2 text-center font-medium">SLA</th>
                    <th className="px-4 py-2 font-medium">Verdict</th>
                    <th className="px-3 py-2 text-center font-medium">Sample</th>
                    <th className="px-4 py-2 font-medium">Method</th>
                    <th className="px-4 py-2 font-medium">Measured</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {data.forges.map((f) => (
                    <tr key={f.forge_cap}>
                      <td className="px-4 py-2 font-mono text-xs text-ink-100">{f.forge_cap}</td>
                      <td
                        className={`px-3 py-2 text-center font-mono ${
                          f.unsafe_to_certify ? "text-danger" : "text-success"
                        }`}
                      >
                        {f.parity_score.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-center font-mono text-ink-400">
                        {f.sla_threshold.toFixed(2)}
                      </td>
                      <td className="px-4 py-2">
                        {f.unsafe_to_certify ? (
                          <span className="rounded bg-danger/15 px-2 py-0.5 text-xs font-semibold text-danger">
                            unsafe_to_certify
                          </span>
                        ) : (
                          <span className="rounded bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">
                            within SLA
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center font-mono text-ink-300">
                        {f.sample_size || "—"}
                      </td>
                      <td className="px-4 py-2 text-xs text-ink-300">{f.method}</td>
                      <td className="px-4 py-2 text-xs text-ink-400">
                        {f.measured_at ? new Date(f.measured_at).toLocaleDateString() : "—"} ·{" "}
                        {f.measured_by}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
              No parity measurements recorded yet. Until a forge is measured it reads as safe —
              record a measurement via <code>POST /api/parity</code> once production telemetry is
              wired up.
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}
