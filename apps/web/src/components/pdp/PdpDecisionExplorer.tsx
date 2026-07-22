"use client";

import { useState } from "react";

import { DecisionPill } from "@/components/common/DecisionPill";
import { pdpDecide, type AgentSummary, type AuthDecision } from "@/lib/api/client";

export function PdpDecisionExplorer({ agents }: { agents: AgentSummary[] }) {
  const [agentId, setAgentId] = useState(agents[0]?.villageAgentId ?? "");
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<AuthDecision | null>(null);

  async function onDecide() {
    setBusy(true);
    setError(null);
    setDecision(null);
    try {
      setDecision(await pdpDecide({ subject_agent_id: agentId, action: action.trim() }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <h2 className="mb-4 text-xl">Decision explorer</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-ink-200">
          Agent
          <select
            value={agentId}
            onChange={(e) => setAgentId(e.target.value)}
            className="min-w-[14rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 text-sm text-ink-50"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.villageAgentId}>
                {a.name} ({a.villageAgentId})
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs text-ink-200">
          Action (Forge capability)
          <input
            value={action}
            onChange={(e) => setAction(e.target.value)}
            placeholder="cre-forge.deal_desk.approve"
            className="min-w-[16rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 font-mono text-sm text-ink-50"
          />
        </label>
        <button
          onClick={onDecide}
          disabled={busy || !agentId || !action.trim()}
          className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
        >
          {busy ? "Deciding…" : "Decide"}
        </button>
      </div>

      {error && <p className="mt-3 text-sm text-danger">{error}</p>}

      {decision && (
        <div className="mt-4 rounded-lg border border-ink-600 bg-ink-900/60 p-4">
          <div className="flex items-center gap-3">
            <DecisionPill decision={decision.decision} />
            <span className="font-mono text-xs text-ink-300">{decision.reason_code}</span>
            <span className="ml-auto text-xs text-ink-400">
              TTL {decision.ttl_seconds}s · fail-{decision.fail_policy}
            </span>
          </div>
          <p className="mt-2 text-sm text-ink-100">{decision.reason_detail}</p>
          {decision.required_approver && (
            <p className="mt-1 text-xs text-warning">
              Requires approver: {decision.required_approver}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
