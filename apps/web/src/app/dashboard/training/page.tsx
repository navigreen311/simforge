import { PageMeta } from "@/components/ui/PageMeta";
import { TrainingQueue } from "@/components/training/TrainingQueue";
import { training, type EnrichedProposal } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function TrainingPage() {
  let proposals: EnrichedProposal[] = [];
  let error: string | null = null;

  try {
    proposals = (await training.enriched()).proposals;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load training proposals";
  }

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Agent Training</h1>
        <PageMeta />
      </div>
      <p className="mb-4 max-w-4xl text-ink-200">
        When an agent does poorly on a scenario in one area, SimForge writes a training proposal — a
        specific tweak to the agent&apos;s prompt aimed at that weakness. You review it. If you
        approve, the agent&apos;s prompt is upgraded to a new version, and any certifications earned
        on the <strong>old</strong> prompt version are suspended, because the agent has effectively
        changed — it must be re-certified on the new version. Nothing is applied without your
        approval (ADR-0026).
      </p>

      {/* Lifecycle indicator */}
      <div className="mb-8 flex flex-wrap items-center gap-2 text-xs text-ink-300">
        {["Weak run detected", "Proposal generated", "Pending review"].map((s, i) => (
          <span key={s} className="flex items-center gap-2">
            {i > 0 && <span className="text-ink-500">→</span>}
            <span className={s === "Pending review" ? "rounded bg-warning/15 px-2 py-0.5 text-warning" : "rounded bg-ink-700 px-2 py-0.5 text-ink-200"}>
              {s}
            </span>
          </span>
        ))}
        <span className="text-ink-500">→</span>
        <span className="rounded bg-success/15 px-2 py-0.5 text-success">
          Approved (prompt promoted, old certs suspended)
        </span>
        <span className="text-ink-500">/</span>
        <span className="rounded bg-ink-600 px-2 py-0.5 text-ink-300">Rejected</span>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load proposals: <code className="text-danger">{error}</code>
        </div>
      ) : proposals.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No training proposals yet. These appear when an agent scores weakly on a scenario.
        </div>
      ) : (
        <TrainingQueue proposals={proposals} />
      )}
    </div>
  );
}
