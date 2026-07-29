"use client";

import { useMemo, useState } from "react";

import { DecisionPill } from "@/components/common/DecisionPill";
import {
  pdpDecide,
  type AgentSummary,
  type AuthDecision,
  type CapabilityLabel,
} from "@/lib/api/client";
import { DECISION_MEANING, drivingFactor, reasonText } from "@/lib/pdp";

export function PdpDecisionExplorer({
  agents,
  caps,
}: {
  agents: AgentSummary[];
  caps: CapabilityLabel[];
}) {
  const [agentId, setAgentId] = useState(agents[0]?.villageAgentId ?? "");
  const [action, setAction] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decision, setDecision] = useState<AuthDecision | null>(null);

  const capByLabel = useMemo(
    () => new Map(caps.map((c) => [c.cap_id, `${c.label} · ${c.forge}`])),
    [caps],
  );
  const typedLabel = capByLabel.get(action.trim());

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
      <h2 className="text-xl">Decision explorer</h2>
      <p className="mb-4 mt-1 text-xs text-ink-400">
        Ask whether an agent may perform a specific action right now. The engine checks the agent&apos;s
        certs, autonomy, and safe-mode and returns a decision with its reason — the real PDP, not a
        simulation.
      </p>
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
          Action (capability — pick a friendly one or type a raw id)
          <input
            value={action}
            onChange={(e) => setAction(e.target.value)}
            list="pdp-caps"
            placeholder="cre-forge.deal_desk.approve"
            className="min-w-[16rem] rounded border border-ink-500 bg-ink-700 px-3 py-2 font-mono text-sm text-ink-50"
          />
          <datalist id="pdp-caps">
            {caps.map((c) => (
              <option key={c.cap_id} value={c.cap_id}>
                {c.label} · {c.forge}
              </option>
            ))}
          </datalist>
          {typedLabel && <span className="text-[11px] text-gold-400">{typedLabel}</span>}
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
          <div className="flex flex-wrap items-center gap-3">
            <DecisionPill decision={decision.decision} />
            <span className="text-sm text-ink-100">
              {DECISION_MEANING[decision.decision] ?? decision.decision}
            </span>
            <span className="ml-auto text-xs text-ink-400">
              TTL {decision.ttl_seconds}s · fail-{decision.fail_policy}
            </span>
          </div>
          <dl className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
            <Fact k="Reason" v={reasonText(decision.reason_code)} title={decision.reason_code} />
            <Fact k="Driven by" v={drivingFactor(decision.reason_code)} />
            <Fact k="Detail" v={decision.reason_detail} />
          </dl>
          {decision.required_approver && (
            <p className="mt-2 text-xs text-warning">
              Requires approver: {decision.required_approver}
            </p>
          )}
          <p className="mt-3 text-[10px] text-ink-500">
            The PDP returns a final decision + reason code, not a step-by-step trace. The “driven by”
            factor above is derived from the reason code; a decision trace would make each check
            (cert → autonomy → safe-mode) explicit.
          </p>
        </div>
      )}
    </div>
  );
}

function Fact({ k, v, title }: { k: string; v: string; title?: string }) {
  return (
    <div className="rounded border border-ink-600 bg-ink-800 px-2 py-1.5" title={title}>
      <dt className="text-ink-400">
        {k}
        {title && <span className="ml-1 font-mono text-[10px] text-ink-500">({title})</span>}
      </dt>
      <dd className="mt-0.5 text-ink-100">{v}</dd>
    </div>
  );
}
