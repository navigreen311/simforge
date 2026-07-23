import { GoldenRunButton } from "@/components/golden/GoldenRunButton";
import { PageMeta } from "@/components/ui/PageMeta";
import { golden, type GoldenBaseline, type GoldenScenario } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const KEY_DIMS = ["p1_correctness", "p5_escalation", "p7_customer_experience", "cognitive_aggregate"];

export default async function GoldenPage() {
  let scenarios: GoldenScenario[] = [];
  let baseline: GoldenBaseline | null = null;
  let error: string | null = null;
  try {
    const [sc, bl] = await Promise.all([golden.scenarios(), golden.baseline()]);
    scenarios = sc.scenarios;
    baseline = bl;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load golden set";
  }

  const tiers = Array.from(new Set(scenarios.map((s) => s.tier)));

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Golden Benchmark</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        A curated set of scenarios with a committed baseline. Running the suite must reproduce the
        baseline exactly under the stub provider — any deviation is a regression in the evaluator
        (ADR-0033).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the golden set: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {/* Coverage */}
          <div className="mb-6 rounded-xl border border-ink-500 bg-ink-800 p-4 text-sm">
            <span className="text-ink-100">
              {scenarios.length} golden scenarios covering {tiers.length} tier
              {tiers.length === 1 ? "" : "s"}:
            </span>{" "}
            <span className="font-mono text-xs text-gold-400">{tiers.join(", ") || "—"}</span>
            {tiers.length < 3 && (
              <span className="ml-2 text-warning">
                ⚠ not all difficulty tiers are covered — regressions at uncovered tiers can slip
                through.
              </span>
            )}
            {baseline?.provider && (
              <span className="ml-2 text-xs text-ink-400">· baseline provider: {baseline.provider}</span>
            )}
          </div>

          {/* Committed baseline */}
          <section className="mb-8">
            <h2 className="mb-3 text-lg">Committed baseline</h2>
            {baseline && Object.keys(baseline.scenarios).length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Scenario</th>
                      <th className="px-4 py-2 font-medium">Outcome</th>
                      <th className="px-4 py-2 font-medium">Gate</th>
                      {KEY_DIMS.map((d) => (
                        <th key={d} className="px-3 py-2 text-center font-mono text-[10px]">
                          {d}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {Object.entries(baseline.scenarios).map(([sid, b]) => (
                      <tr key={sid}>
                        <td className="px-4 py-2 font-mono text-xs text-gold-400">{sid}</td>
                        <td className="px-4 py-2 text-ink-100">{b.outcome ?? "—"}</td>
                        <td className="px-4 py-2">
                          <span className={b.gate_passed ? "text-success" : "text-ink-300"}>
                            {b.gate_passed === null ? "—" : b.gate_passed ? "pass" : "fail"}
                          </span>
                        </td>
                        {KEY_DIMS.map((d) => (
                          <td key={d} className="px-3 py-2 text-center text-xs text-ink-200">
                            {typeof b.dims[d] === "number" ? (b.dims[d] as number).toFixed(2) : String(b.dims[d] ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
                No committed baseline found. Generate it with{" "}
                <code>python scripts/golden-baseline.py</code>.
              </div>
            )}
          </section>

          {/* Run + result */}
          <section>
            <h2 className="mb-3 text-lg">Regression check</h2>
            <GoldenRunButton />
          </section>
        </>
      )}
    </div>
  );
}
