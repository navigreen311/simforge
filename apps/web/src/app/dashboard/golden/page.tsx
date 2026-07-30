import Link from "next/link";

import { GoldenRunButton } from "@/components/golden/GoldenRunButton";
import { CopyButton } from "@/components/ui/CopyButton";
import { PageMeta } from "@/components/ui/PageMeta";
import { VerifiedState, verdictFor } from "@/components/ui/VerifiedState";
import {
  golden,
  type GoldenBaseline,
  type GoldenNomination,
  type GoldenRunHistoryEntry,
  type GoldenScenario,
} from "@/lib/api/client";
import { describeDimension } from "@/lib/dimensions";

export const dynamic = "force-dynamic";

const KEY_DIMS = ["p1_correctness", "p5_escalation", "p7_customer_experience", "cognitive_aggregate"];
const TOTAL_TIERS = 3; // foundational · intermediate · advanced_crisis

// A diff dim can be a rubric dimension or the outcome/gate meta-fields.
function diffLabel(dim: string): string {
  if (dim === "outcome") return "Outcome";
  if (dim === "gate_passed") return "Gate";
  return describeDimension(dim).name;
}

export default async function GoldenPage() {
  let scenarios: GoldenScenario[] = [];
  let baseline: GoldenBaseline | null = null;
  let history: GoldenRunHistoryEntry[] = [];
  let nominations: GoldenNomination[] = [];
  let error: string | null = null;
  try {
    const [sc, bl, hist, noms] = await Promise.all([
      golden.scenarios(),
      golden.baseline(),
      golden.runHistory(),
      golden.nominations(),
    ]);
    scenarios = sc.scenarios;
    baseline = bl;
    history = hist.runs;
    nominations = noms.nominations;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load golden set";
  }

  const tiers = Array.from(new Set(scenarios.map((s) => s.tier)));
  // Titles for both the committed-baseline ids and the current golden set (a run's results use the
  // current set; the baseline table uses the baseline ids — they can differ if the set drifted).
  const titleFor = new Map<string, string>([
    ...Object.entries(baseline?.titles ?? {}),
    ...scenarios.map((s) => [s.scenario_id, s.title] as [string, string]),
  ]);
  const lastRun = history[0] ?? null;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Golden Benchmark</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        A golden benchmark is a fixed set of scenarios with known, locked-in expected results.
        Because the stub scorer is deterministic, running these scenarios should reproduce the
        committed results <strong>exactly</strong> every time. If a run produces different numbers,
        the scoring engine itself has changed — that&apos;s a regression in the evaluator, caught
        before it can corrupt real certifications. This is how SimForge tests itself (ADR-0033).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the golden set: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {/* Regression check — the actionable core, first. */}
          <section className="mb-8">
            <h2 className="mb-3 text-lg">Regression check</h2>
            <GoldenRunButton />
            <div className="mt-3">
              {lastRun ? (
                <ResultPanel run={lastRun} titleFor={titleFor} />
              ) : (
                <p className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
                  Not run yet. Click <strong>Run golden suite</strong> to check the scoring engine
                  against the committed baseline.
                </p>
              )}
            </div>

            {history.length > 1 && (
              <div className="mt-4">
                <h3 className="mb-2 text-xs uppercase tracking-wide text-ink-400">Run history</h3>
                <ul className="flex flex-col gap-1 text-xs">
                  {history.map((r) => (
                    <li key={r.id} className="flex items-center gap-3">
                      <span className={`rounded px-2 py-0.5 font-semibold ${r.passed ? "bg-success/15 text-success" : r.total === 0 ? "bg-warning/15 text-warning" : "bg-danger/15 text-danger"}`}>
                        {r.passed ? "PASS" : r.total === 0 ? "INDETERMINATE" : "FAIL"}
                      </span>
                      <span className="text-ink-300">{r.matched}/{r.total} match</span>
                      <span className="text-ink-500">{r.ran_at ? new Date(r.ran_at).toLocaleString() : "—"}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {/* Coverage + actionable next step (STEP 5/6). */}
          <div className="mb-6 rounded-xl border border-ink-500 bg-ink-800 p-4 text-sm">
            <span className="text-ink-100">
              {scenarios.length} golden scenarios · {tiers.length} of {TOTAL_TIERS} tiers covered:
            </span>{" "}
            <span className="font-mono text-xs text-gold-400">{tiers.join(", ") || "—"}</span>
            {tiers.length < TOTAL_TIERS && (
              <p className="mt-2 text-warning">
                ⚠ Only the {tiers.join(", ")} tier{tiers.length === 1 ? " has" : "s have"} golden
                scenarios. Foundational and Intermediate runs aren&apos;t regression-protected — a
                scoring change at those tiers wouldn&apos;t be caught here. To close this, commit
                golden scenarios at the other tiers from the{" "}
                <Link href="/dashboard/scenario-bank" className="underline hover:text-warning/80">
                  Scenario Bank
                </Link>
                .
              </p>
            )}
          </div>

          {/* Baseline provenance (STEP 4). */}
          {baseline && (
            <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-xl border border-ink-500 bg-ink-800 p-4 text-xs text-ink-300">
              <span className="text-ink-200" title="The locked reference these runs are checked against.">
                Committed baseline
              </span>
              <span>
                by <span className="text-ink-100">{baseline.committed_by ?? "—"}</span>
              </span>
              <span>
                on{" "}
                <span className="text-ink-100">
                  {baseline.committed_at ? new Date(baseline.committed_at).toLocaleDateString() : "—"}
                </span>
              </span>
              <span>
                provider <span className="text-ink-100">{baseline.provider ?? "—"}</span>
              </span>
              {baseline.hash && (
                <span className="flex items-center gap-1">
                  hash <span className="font-mono text-ink-100">{baseline.hash.slice(0, 12)}…</span>
                  <CopyButton value={baseline.hash} label="copy" />
                </span>
              )}
            </div>
          )}

          {/* Committed baseline table (STEP 2). */}
          <section className="mb-8">
            <h2 className="mb-1 text-lg">Committed baseline</h2>
            <p className="mb-3 text-xs text-ink-400">
              These are the expected values. Running the suite compares fresh results against them.
            </p>
            {baseline && Object.keys(baseline.scenarios).length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Scenario</th>
                      <th className="px-4 py-2 font-medium">
                        <span className="cursor-help underline decoration-ink-500 decoration-dotted underline-offset-4" title="The scenario ran to a terminal resolved state.">
                          Outcome
                        </span>
                      </th>
                      <th className="px-4 py-2 font-medium">
                        <span className="cursor-help underline decoration-ink-500 decoration-dotted underline-offset-4" title="Whether this scenario is expected to PASS or FAIL certification. A scenario whose expected result is 'fail' is SUPPOSED to fail — that's the correct baseline, not a problem.">
                          Gate
                        </span>
                      </th>
                      {KEY_DIMS.map((d) => (
                        <th key={d} className="px-3 py-2 text-center font-medium">
                          <span className="cursor-help underline decoration-ink-500 decoration-dotted underline-offset-4" title={`${describeDimension(d).tip} The exact expected score for this dimension — a real run must reproduce this value.`}>
                            {describeDimension(d).name}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {Object.entries(baseline.scenarios).map(([sid, b]) => (
                      <tr key={sid}>
                        <td className="px-4 py-2">
                          <div className="text-ink-50">{titleFor.get(sid) ?? sid}</div>
                          <div className="font-mono text-[10px] text-ink-500">{sid}</div>
                        </td>
                        <td className="px-4 py-2 text-ink-100">{b.outcome ?? "—"}</td>
                        <td className="px-4 py-2">
                          {b.gate_passed === null ? (
                            <span className="text-ink-300">—</span>
                          ) : b.gate_passed ? (
                            <span className="text-success">pass</span>
                          ) : (
                            <span className="text-ink-200" title="Expected to fail — this is the intended baseline outcome, not a broken test.">
                              fail (expected)
                            </span>
                          )}
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

          {/* Gold-set governance (§12.5): nomination + council review + freeze. */}
          <section className="mb-4">
            <h2 className="mb-1 text-lg">Gold-set governance</h2>
            <p className="mb-3 max-w-4xl text-xs text-ink-400">
              The gold set is immutable, so a scenario joins it only by formal nomination reviewed by
              the benchmark refresh council (Ivan · Administrator · Acquisitions Principal · a senior
              engineer). A scenario&apos;s <code>isGolden</code> flag flips only when the review
              request is approved by quorum — never by hand (§12.5).
            </p>
            {nominations.length > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Scenario</th>
                      <th className="px-4 py-2 font-medium">Nominated by</th>
                      <th className="px-4 py-2 font-medium">IRR</th>
                      <th className="px-4 py-2 font-medium">Status</th>
                      <th className="px-4 py-2 font-medium">Frozen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {nominations.map((n) => (
                      <tr key={n.id}>
                        <td className="px-4 py-2">
                          <div className="text-ink-50">{titleFor.get(n.scenario_id) ?? n.scenario_id}</div>
                          <div className="font-mono text-[10px] text-ink-500">{n.scenario_id}</div>
                        </td>
                        <td className="px-4 py-2 text-ink-200">{n.nominated_by}</td>
                        <td className="px-4 py-2 font-mono text-xs text-ink-300">
                          {n.inter_rater_reliability != null
                            ? n.inter_rater_reliability.toFixed(2)
                            : "—"}
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-semibold ${
                              n.status === "frozen"
                                ? "bg-success/15 text-success"
                                : n.status === "pending"
                                  ? "bg-warning/15 text-warning"
                                  : "bg-ink-600 text-ink-200"
                            }`}
                          >
                            {n.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-xs text-ink-400">
                          {n.frozen_at
                            ? `${new Date(n.frozen_at).toLocaleDateString()} · ${n.frozen_by}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
                No gold-set nominations yet. Nominations open a council review request via the
                Approvals workflow before any scenario can be frozen into the bank.
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function ResultPanel({
  run,
  titleFor,
}: {
  run: GoldenRunHistoryEntry;
  titleFor: Map<string, string>;
}) {
  const verdict = run.total === 0 ? "indeterminate" : verdictFor(run.total, run.regressions);
  const asOf = run.ran_at ? new Date(run.ran_at).toLocaleString() : undefined;
  const failing = run.results.filter((r) => r.status === "regression" || r.status === "missing");

  return (
    <VerifiedState
      verdict={verdict}
      checked={run.total}
      asOf={asOf}
      passText={`All ${run.total} golden scenarios reproduced their committed baseline exactly. The scoring engine is stable — no regression.`}
      failText={`Regression detected — ${run.regressions} scenario(s) deviated from baseline.`}
    >
      {verdict === "indeterminate" && (
        <p className="text-xs text-ink-200">0 scenarios ran, so this cannot be a pass.</p>
      )}
      {verdict === "fail" && (
        <div className="flex flex-col gap-3">
          {failing.map((r) => (
            <div key={r.scenario_id} className="rounded-lg border border-danger/30 bg-ink-900/40 p-3">
              <div className="mb-2 text-sm text-ink-50">
                {titleFor.get(r.scenario_id) ?? r.scenario_id}{" "}
                <span className="font-mono text-[10px] text-ink-500">{r.scenario_id}</span>
              </div>
              {r.status === "missing" ? (
                <p className="text-xs text-warning">Baseline scenario produced no run.</p>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead className="text-ink-400">
                    <tr>
                      <th className="py-1 font-normal">Dimension</th>
                      <th className="py-1 font-normal">Expected</th>
                      <th className="py-1 font-normal">Actual</th>
                    </tr>
                  </thead>
                  <tbody>
                    {r.diffs.map((d) => (
                      <tr key={d.dim}>
                        <td className="py-0.5 text-ink-200">{diffLabel(d.dim)}</td>
                        <td className="py-0.5 font-mono text-ink-300">{String(d.expected)}</td>
                        <td className="py-0.5 font-mono text-danger">{String(d.actual)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      )}
    </VerifiedState>
  );
}
