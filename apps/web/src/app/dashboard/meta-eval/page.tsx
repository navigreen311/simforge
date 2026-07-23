import Link from "next/link";

import { MetaEvalTable } from "@/components/metaeval/MetaEvalTable";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, metaEval, type MetaEvalReport, type PackSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const JUDGE_DIMS = new Set(["p7_customer_experience", "c1_breath_coherence", "c2_soul_stability"]);

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

  // Zero-variance HEURISTIC dims — the ones the stub banner does NOT explain.
  const heuristicZeroVar = report
    ? report.dimensions.filter(
        (d) => !JUDGE_DIMS.has(d.dim) && d.stddev !== null && d.stddev < 0.001 && d.n > 1,
      )
    : [];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Meta-Eval</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Evaluating the evaluator — per-dimension variance + discrimination (mean when passed − mean
        when failed). Flagged dims carry no signal (ADR-0027).
      </p>

      <div className="mb-6 flex flex-wrap gap-2 text-xs">
        <Link
          href="/dashboard/meta-eval"
          className={`rounded-full px-3 py-1 ${!packId ? "bg-gold-500 text-ink-900" : "bg-ink-700 text-ink-100 hover:bg-ink-600"}`}
        >
          All packs
        </Link>
        {packs.map((p) => (
          <Link
            key={p.packId}
            href={`/dashboard/meta-eval?pack=${p.packId}`}
            className={`rounded-full px-3 py-1 ${packId === p.packId ? "bg-gold-500 text-ink-900" : "bg-ink-700 text-ink-100 hover:bg-ink-600"}`}
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
          No scorecards {packId ? "for this pack " : ""}yet.
        </div>
      ) : report ? (
        <>
          {/* Rubric-integrity blocking banner (P0-B Finding 1). */}
          {heuristicZeroVar.length >= 3 && (
            <div className="mb-6 rounded-xl border border-danger/50 bg-danger/15 p-4 text-sm text-ink-50">
              <div className="font-semibold text-danger">⚠ Rubric integrity warning</div>
              <p className="mt-1">
                {heuristicZeroVar.length} of {report.dimensions.length} dimensions show{" "}
                <strong>zero variance</strong> across {report.n_scorecards} scorecards
                {packId ? " (this pack)" : ""}. Certification decisions may be driven by a single
                dimension. These are <strong>heuristic</strong> scorers returning a constant on the
                current uniform (all-passed sandbox) run population — <em>not</em> the stub-judge
                dims, so the stub-mode banner does not explain them.
              </p>
              <p className="mt-1 font-mono text-[11px] text-ink-300">
                zero-variance heuristics: {heuristicZeroVar.map((d) => d.dim).join(", ")}
              </p>
            </div>
          )}

          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Scorecards" value={report.n_scorecards} />
            <Stat label="Pass rate" value={`${(report.pass_rate * 100).toFixed(0)}%`} sub={`${report.n_passed}✓ ${report.n_failed}✗`} />
            <Stat label="Numeric dims" value={report.dimensions.length} />
            <Stat label="Flagged" value={report.flagged_dimensions.length} danger={report.flagged_dimensions.length > 0} />
          </div>

          <MetaEvalTable dimensions={report.dimensions} />

          {/* p2 / c4 explanation (Phase 0 D5). */}
          <p className="mt-4 rounded-lg border border-ink-600 bg-ink-800 p-3 text-xs text-ink-300">
            <strong className="text-ink-100">Why no p2 / c4?</strong> p2_compliance is a boolean and
            c4_arc_narrative_coherence is categorical — neither is a numeric dimension, so both are
            excluded from this variance/discrimination table by design (they are gate inputs, scored
            elsewhere). They exist in the rubric; they are not silently dropped.
          </p>
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value, sub, danger }: { label: string; value: string | number; sub?: string; danger?: boolean }) {
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <div className="text-sm text-ink-200">{label}</div>
      <div className={`mt-2 font-display text-3xl ${danger ? "text-danger" : "text-gold-500"}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-ink-300">{sub}</div>}
    </div>
  );
}
