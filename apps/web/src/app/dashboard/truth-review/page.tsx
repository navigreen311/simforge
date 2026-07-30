import Link from "next/link";

import { PageMeta } from "@/components/ui/PageMeta";
import {
  truthReview,
  type TruthReviewChecklist,
  type TruthReviewUnreviewed,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

const DIM_LABEL: Record<string, string> = {
  realistic: "Realistic",
  outcome_correct: "Expected outcome correct",
  no_fabrication: "No fabricated facts",
  compliance_accurate: "Compliance mapping accurate",
};

export default async function TruthReviewPage() {
  let checklist: TruthReviewChecklist | null = null;
  let unreviewed: TruthReviewUnreviewed | null = null;
  let error: string | null = null;
  try {
    const [c, u] = await Promise.all([truthReview.checklist(), truthReview.unreviewed()]);
    checklist = c;
    unreviewed = u;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load truth-review data";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Scenario Truth Review</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        A scenario can only certify agents if it faithfully represents reality. A reviewer affirms a
        checklist before the scenario is trusted; the review is approved only when every dimension
        holds. This is the reviewer worklist (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load truth-review data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <div className="mb-6 rounded-xl border border-ink-500 bg-ink-800 p-4 text-sm">
            <div className="mb-2 text-ink-100">Truth checklist — all must hold to approve:</div>
            <ul className="flex flex-wrap gap-2">
              {checklist?.dimensions.map((d) => (
                <li
                  key={d}
                  className="rounded bg-ink-700 px-2 py-1 font-mono text-xs text-ink-100"
                >
                  {DIM_LABEL[d] ?? d}
                </li>
              ))}
            </ul>
            <div className="mt-3 text-xs">
              Gate enforcement:{" "}
              {checklist?.enforced ? (
                <span className="font-semibold text-danger">
                  ON — unreviewed scenarios cannot run
                </span>
              ) : (
                <span className="text-ink-300">
                  off (worklist-only; set TRUTH_GATE_ENFORCE to block unreviewed runs)
                </span>
              )}
            </div>
          </div>

          <section>
            <h2 className="mb-1 text-lg">Awaiting truth review</h2>
            <p className="mb-3 text-xs text-ink-400">
              Scenarios without an approved review. Submit one via{" "}
              <code>POST /api/truth-review/{"{scenario_id}"}</code>.
            </p>
            {unreviewed && unreviewed.total > 0 ? (
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Scenario</th>
                      <th className="px-4 py-2 font-medium">Review status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {unreviewed.scenario_ids.map((sid) => (
                      <tr key={sid}>
                        <td className="px-4 py-2 font-mono text-xs text-ink-100">{sid}</td>
                        <td className="px-4 py-2">
                          <span className="rounded bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">
                            needs review
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-success">
                Every ingested scenario has an approved truth review. Import more from the{" "}
                <Link href="/dashboard/scenario-bank" className="underline">
                  Scenario Bank
                </Link>
                .
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
