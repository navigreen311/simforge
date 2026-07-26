import Link from "next/link";

import { BankExplorer } from "@/components/scenario-bank/BankExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { scenarioBank, type BankScenario } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ScenarioBankPage() {
  let scenarios: BankScenario[] = [];
  let awaitingReview = 0;
  let total = 0;
  let error: string | null = null;
  try {
    const [list, counts] = await Promise.all([scenarioBank.list(), scenarioBank.counts()]);
    scenarios = list.items;
    total = list.total;
    awaitingReview = counts.awaiting_review;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load the scenario bank";
  }

  return (
    <div className="mx-auto max-w-[90rem]">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Scenario Bank</h1>
        <div className="flex items-center gap-3">
          <PageMeta />
          <Link
            href="/dashboard/scenario-bank/new"
            className="rounded bg-gold-500 px-3 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400"
          >
            + New scenario
          </Link>
        </div>
      </div>
      <p className="mb-4 text-ink-200">
        The reviewable library of certification scenarios. Ingested and AI-drafted scenarios land as
        <strong> drafts</strong> and require a human to review and commit — nothing enters
        certification automatically.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <span
              className={`rounded-full px-3 py-1 text-sm font-semibold ${
                awaitingReview > 0 ? "bg-warning/20 text-warning" : "bg-ink-700 text-ink-300"
              }`}
            >
              {awaitingReview} draft{awaitingReview === 1 ? "" : "s"} awaiting review
            </span>
            <span className="text-xs text-ink-400">{total} scenarios in the bank</span>
          </div>
          <BankExplorer scenarios={scenarios} />
        </>
      )}
    </div>
  );
}
