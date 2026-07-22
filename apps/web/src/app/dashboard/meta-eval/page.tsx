import Link from "next/link";

import { api, metaEval, type MetaEvalReport, type PackSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

function fmt(v: number | null, digits = 2): string {
  return v === null || v === undefined ? "—" : v.toFixed(digits);
}

function FlagPill({ flag }: { flag: string }) {
  const styles: Record<string, string> = {
    constant: "bg-danger/15 text-danger",
    non_discriminating: "bg-warning/20 text-warning",
    insufficient_data: "bg-ink-600 text-ink-300",
    no_data: "bg-ink-600 text-ink-300",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-[11px] ${styles[flag] ?? "bg-ink-600 text-ink-100"}`}>
      {flag}
    </span>
  );
}

export default async function MetaEvalPage({
  searchParams,
}: {
  searchParams: { pack?: string };
}) {
  const packId = searchParams.pack;
  let report: MetaEvalReport | null = null;
  let packs: PackSummary[] = [];
  let error: string | null = null;

  try {
    const [rep, packList] = await Promise.all([metaEval.report(packId), api.packs()]);
    report = rep;
    packs = packList.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load meta-eval";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-3xl">Meta-Eval</h1>
      <p className="mb-6 text-ink-200">
        Evaluating the evaluator — per-dimension variance and discrimination (mean when passed −
        mean when failed) across the scorecard population. Flagged dimensions carry no signal
        (ADR-0027).
      </p>

      <div className="mb-6 flex flex-wrap gap-2 text-xs">
        <Link
          href="/dashboard/meta-eval"
          className={`rounded-full px-3 py-1 ${
            !packId ? "bg-gold-500 text-ink-900" : "bg-ink-700 text-ink-100 hover:bg-ink-600"
          }`}
        >
          All packs
        </Link>
        {packs.map((p) => (
          <Link
            key={p.packId}
            href={`/dashboard/meta-eval?pack=${p.packId}`}
            className={`rounded-full px-3 py-1 ${
              packId === p.packId
                ? "bg-gold-500 text-ink-900"
                : "bg-ink-700 text-ink-100 hover:bg-ink-600"
            }`}
          >
            {p.name}
          </Link>
        ))}
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load meta-eval: <code className="text-danger">{error}</code>
        </div>
      ) : report && report.n_scorecards === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No scorecards {packId ? "for this pack " : ""}yet. Run scenarios to populate the eval
          population.
        </div>
      ) : report ? (
        <>
          <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Scorecards</div>
              <div className="mt-2 font-display text-3xl text-gold-500">{report.n_scorecards}</div>
            </div>
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Pass rate</div>
              <div className="mt-2 font-display text-3xl text-gold-500">
                {(report.pass_rate * 100).toFixed(0)}%
              </div>
              <div className="mt-1 text-xs text-ink-300">
                {report.n_passed} passed · {report.n_failed} failed
              </div>
            </div>
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Dimensions</div>
              <div className="mt-2 font-display text-3xl text-gold-500">
                {report.dimensions.length}
              </div>
            </div>
            <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="text-sm text-ink-200">Flagged</div>
              <div
                className={`mt-2 font-display text-3xl ${
                  report.flagged_dimensions.length > 0 ? "text-danger" : "text-success"
                }`}
              >
                {report.flagged_dimensions.length}
              </div>
              <div className="mt-1 text-xs text-ink-300">no-signal dims</div>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-ink-500">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-ink-800 text-ink-200">
                <tr>
                  <th className="px-4 py-3 font-medium">Dimension</th>
                  <th className="px-4 py-3 font-medium">n</th>
                  <th className="px-4 py-3 font-medium">Mean</th>
                  <th className="px-4 py-3 font-medium">Std</th>
                  <th className="px-4 py-3 font-medium">Passed</th>
                  <th className="px-4 py-3 font-medium">Failed</th>
                  <th className="px-4 py-3 font-medium">Discrimination</th>
                  <th className="px-4 py-3 font-medium">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-ink-600">
                {report.dimensions.map((d) => {
                  const noSignal = d.flags.some(
                    (f) => f === "constant" || f === "non_discriminating",
                  );
                  return (
                    <tr key={d.dim} className={noSignal ? "bg-danger/5" : "hover:bg-ink-800/60"}>
                      <td className="px-4 py-3 font-mono text-xs text-gold-400">{d.dim}</td>
                      <td className="px-4 py-3 text-ink-200">{d.n}</td>
                      <td className="px-4 py-3 text-ink-100">{fmt(d.mean)}</td>
                      <td className="px-4 py-3 text-ink-100">{fmt(d.stddev, 3)}</td>
                      <td className="px-4 py-3 text-ink-200">{fmt(d.mean_passed)}</td>
                      <td className="px-4 py-3 text-ink-200">{fmt(d.mean_failed)}</td>
                      <td
                        className={`px-4 py-3 font-medium ${
                          d.discrimination !== null && Math.abs(d.discrimination) < 0.05
                            ? "text-warning"
                            : "text-ink-50"
                        }`}
                      >
                        {fmt(d.discrimination)}
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex flex-wrap gap-1">
                          {d.flags.map((f) => (
                            <FlagPill key={f} flag={f} />
                          ))}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
