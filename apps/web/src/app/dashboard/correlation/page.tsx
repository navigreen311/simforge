import { PageMeta } from "@/components/ui/PageMeta";
import { productionOutcomes, type CorrelationReport } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const KIND_LABEL: Record<string, string> = {
  cert_overstates_readiness: "Cert overstates readiness",
  under_certified: "Under-certified",
};

export default async function CorrelationPage() {
  let report: CorrelationReport | null = null;
  let error: string | null = null;
  try {
    report = await productionOutcomes.correlation();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load correlation";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Production Outcome Correlation</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        A certification is a prediction that an agent will perform in production. This closes the
        loop: recorded production outcomes are compared against certification status to catch
        miscalibration — a certified agent that underperforms, or an uncertified agent that excels.
        Production data is an external seam recorded explicitly; scores are never fabricated (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load correlation: <code className="text-danger">{error}</code>
        </div>
      ) : report && report.measured_pairs === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          No production outcomes recorded yet. Record them via{" "}
          <code>POST /api/production-outcomes</code> once production telemetry is available — until
          then there is nothing to correlate (and nothing is assumed).
        </div>
      ) : report ? (
        <>
          <div className="mb-6 flex flex-wrap gap-3">
            <Stat label="Measured pairs" value={report.measured_pairs} />
            <Stat label="Aligned" value={report.summary.aligned ?? 0} tone="ok" />
            <Stat
              label="Miscalibrated"
              value={report.summary.miscalibrated ?? 0}
              tone={report.summary.miscalibrated ? "bad" : "ok"}
            />
          </div>

          {report.findings.length > 0 ? (
            <div className="flex flex-col gap-3">
              {report.findings.map((f, i) => (
                <div
                  key={i}
                  className={`rounded-xl border p-4 ${
                    f.kind === "cert_overstates_readiness"
                      ? "border-danger/30 bg-danger/5"
                      : "border-warning/30 bg-warning/5"
                  }`}
                >
                  <div className="mb-1 flex flex-wrap items-center gap-3">
                    <span className="font-mono text-xs text-ink-100">{f.agent}</span>
                    <span className="font-mono text-xs text-ink-400">{f.forge_cap}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-semibold ${
                        f.kind === "cert_overstates_readiness"
                          ? "bg-danger/15 text-danger"
                          : "bg-warning/15 text-warning"
                      }`}
                    >
                      {KIND_LABEL[f.kind] ?? f.kind}
                    </span>
                    <span className="ml-auto font-mono text-sm text-ink-200">
                      prod {f.outcome_score.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-sm text-ink-200">{f.detail}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-success">
              All measured agent/capability pairs are aligned — certifications match production
              reality.
            </div>
          )}
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "ok" | "bad" }) {
  const color = tone === "bad" ? "text-danger" : tone === "ok" ? "text-success" : "text-ink-50";
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 px-4 py-3">
      <div className={`font-display text-2xl ${color}`}>{value}</div>
      <div className="text-xs text-ink-400">{label}</div>
    </div>
  );
}
