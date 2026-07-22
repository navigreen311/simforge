import { ProposalActions } from "@/components/training/ProposalActions";
import { api, training, type AgentSummary, type TrainingProposal } from "@/lib/api/client";

export const dynamic = "force-dynamic";

function StatusPill({ status }: { status: string }) {
  const styles: Record<string, string> = {
    proposed: "bg-warning/20 text-warning",
    approved: "bg-success/15 text-success",
    rejected: "bg-ink-600 text-ink-300",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${styles[status] ?? "bg-ink-600"}`}>
      {status}
    </span>
  );
}

export default async function TrainingPage() {
  let proposals: TrainingProposal[] = [];
  let agents: AgentSummary[] = [];
  let error: string | null = null;

  try {
    const [props, agentList] = await Promise.all([
      training.proposals(),
      api.agents({ page_size: 200 }),
    ]);
    proposals = props;
    agents = agentList.items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load training proposals";
  }
  const nameById = new Map(agents.map((a) => [a.id, a.villageAgentId]));

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Agent Training</h1>
      <p className="mb-8 text-ink-200">
        A weak run yields a training proposal. Approval promotes the prompt version and suspends
        certs pinned to the old version for re-certification — human-gated (ADR-0026).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load proposals: <code className="text-danger">{error}</code>
        </div>
      ) : proposals.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No training proposals. Generate one from a weak run via{" "}
          <code>POST /api/training/proposals/from-run/&lt;run_id&gt;</code>.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {proposals.map((p) => (
            <div key={p.id} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-mono text-sm text-ink-50">
                  {nameById.get(p.agentId) ?? p.agentId}
                </span>
                <StatusPill status={p.status} />
                <span className="font-mono text-xs text-ink-300">
                  {p.currentPromptVersion} → {p.proposedPromptVersion}
                </span>
                {p.autoApplied && (
                  <span className="rounded bg-info/15 px-2 py-0.5 text-xs text-info">
                    auto-applied
                  </span>
                )}
                <span className="ml-auto">
                  {p.status === "proposed" && <ProposalActions proposalId={p.id} />}
                  {p.reviewedBy && (
                    <span className="text-xs text-ink-400">reviewed by {p.reviewedBy}</span>
                  )}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap gap-1">
                {p.weakDims.map((d) => (
                  <span
                    key={d}
                    className="rounded bg-danger/10 px-2 py-0.5 font-mono text-[11px] text-danger"
                  >
                    {d}
                  </span>
                ))}
              </div>

              <p className="mt-3 text-sm text-ink-100">{p.rationale}</p>
              <p className="mt-2 border-l-2 border-gold-600/40 pl-3 text-sm text-ink-200">
                {p.proposedRefinement}
              </p>
              {p.runId && (
                <p className="mt-2 font-mono text-[11px] text-ink-400">from run {p.runId}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
