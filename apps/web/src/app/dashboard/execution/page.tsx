import { LedgerView } from "@/components/execution/LedgerView";
import { PageMeta } from "@/components/ui/PageMeta";
import { execution, type IntegratedLedger } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function ExecutionPage() {
  let ledger: IntegratedLedger | null = null;
  let error: string | null = null;
  try {
    ledger = await execution.ledger();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load execution data";
  }

  const enabled = ledger?.integrated_execution_enabled ?? false;
  const runs = ledger?.runs ?? [];

  return (
    <div className="mx-auto max-w-7xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Integrated Execution</h1>
        <PageMeta />
      </div>

      {/* STEP 1 — the stakes, in plain language. */}
      <p className="mb-4 max-w-4xl text-ink-200">
        Integrated execution is where agent actions stop being practice and actually happen in real
        systems. When it&apos;s ON, a passing agent&apos;s action — releasing funds, assigning a
        deal, sending a message — is committed for real. Every action is first checked by the policy
        engine (PDP): <strong className="text-success">denied actions are blocked</strong> and never
        commit; <strong className="text-ink-50">allowed actions are applied</strong> and recorded in
        an auditable, reversible ledger. It is OFF by default so nothing commits by accident.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load execution data: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {/* STEP 5 — the deployment setting as a labelled status, not a raw env string. */}
          <div
            className={`mb-6 flex flex-wrap items-center gap-3 rounded-xl border p-4 ${
              enabled ? "border-warning/40 bg-warning/10" : "border-ink-500 bg-ink-800"
            }`}
          >
            <span
              className={`h-3 w-3 rounded-full ${enabled ? "bg-warning" : "bg-ink-300"}`}
              aria-hidden
            />
            <span className="text-sm text-ink-50">
              Deployment setting:{" "}
              <strong className={enabled ? "text-warning" : "text-ink-100"}>
                integrated execution {enabled ? "ENABLED" : "disabled"}
              </strong>
              .{" "}
              {enabled
                ? "Allowed agent actions can commit to real systems on this deployment."
                : "Currently OFF — no agent action can commit to a real system on this deployment. The ledger below is a record of what was evaluated when runs executed."}
            </span>
          </div>

          {/* STEP 2 — the decision → outcome chain, framed as the safety proof. */}
          <div className="mb-8 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-success/30 bg-success/5 p-4 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <DecisionArrow decision="Deny" outcome="blocked" tone="good" />
              </div>
              <p className="text-ink-200">
                The policy engine denied the action, so it was <strong>blocked</strong> and never
                committed. This is the gate working — a bad action was stopped.
              </p>
            </div>
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm">
              <div className="mb-1 flex items-center gap-2">
                <DecisionArrow decision="Allow" outcome="applied" tone="neutral" />
              </div>
              <p className="text-ink-200">
                The policy engine allowed the action, so it was <strong>applied</strong> and recorded
                in the auditable, reversible ledger.
              </p>
            </div>
          </div>

          <h2 className="mb-1 text-xl">Action ledger</h2>
          <p className="mb-4 text-xs text-ink-400">
            Each row is one agent action evaluated during an integrated run, grouped by run. The PDP
            decision shown is what was recorded at run time. Entries tagged{" "}
            <span className="text-warning">historical</span> were recorded before the agent&apos;s
            cert status changed and do not reflect current permissions.
          </p>

          {runs.length === 0 ? (
            <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
              No integrated-execution runs with committed actions yet. Sandbox runs never write, so
              they don&apos;t appear here.
            </div>
          ) : (
            <LedgerView runs={runs} />
          )}
        </>
      )}
    </div>
  );
}

function DecisionArrow({
  decision,
  outcome,
  tone,
}: {
  decision: string;
  outcome: string;
  tone: "good" | "neutral";
}) {
  return (
    <span className="flex items-center gap-2 text-xs font-semibold">
      <span
        className={`rounded px-2 py-0.5 ${
          decision === "Deny" ? "bg-danger/15 text-danger" : "bg-success/15 text-success"
        }`}
      >
        {decision}
      </span>
      <span className="text-ink-400" aria-hidden>
        →
      </span>
      <span
        className={`rounded px-2 py-0.5 ${
          tone === "good" ? "bg-success/15 text-success" : "bg-ink-600 text-ink-100"
        }`}
      >
        {outcome}
      </span>
    </span>
  );
}
