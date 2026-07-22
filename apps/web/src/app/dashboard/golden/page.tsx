import { GoldenRunButton } from "@/components/golden/GoldenRunButton";
import { golden, type GoldenScenario } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function GoldenPage() {
  let scenarios: GoldenScenario[] = [];
  let error: string | null = null;
  try {
    scenarios = (await golden.scenarios()).scenarios;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load golden set";
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl">Golden Benchmark</h1>
      <p className="mb-8 text-ink-200">
        A curated set of scenarios with a committed expected baseline. Running the suite reproduces
        the baseline exactly under the stub provider — any deviation is a regression in the evaluator
        (ADR-0033).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the golden set: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <section className="mb-8">
            <h2 className="mb-3 text-lg">Golden scenarios</h2>
            {scenarios.length === 0 ? (
              <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
                No golden scenarios registered. Mark scenarios with <code>is_golden: true</code> in
                their pack.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {scenarios.map((s) => (
                  <div
                    key={s.scenario_id}
                    className="flex items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-sm"
                  >
                    <span className="font-mono text-xs text-gold-400">{s.scenario_id}</span>
                    <span className="flex-1 text-ink-50">{s.title}</span>
                    <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-200">
                      {s.tier}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h2 className="mb-3 text-lg">Regression check</h2>
            <GoldenRunButton />
          </section>
        </>
      )}
    </div>
  );
}
