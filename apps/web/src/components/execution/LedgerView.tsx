"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { DecisionPill } from "@/components/common/DecisionPill";
import { CopyButton } from "@/components/ui/CopyButton";
import { type LedgerRun } from "@/lib/api/client";
import { reasonText } from "@/lib/pdp";

// The safety chain, in words. The recorded PDP decision determines whether a real action committed.
function whatThisMeans(a: LedgerRun["actions"][number]): string {
  if (a.reverted) {
    return "This action was applied, then reversed with a compensating ledger entry — the effect no longer stands.";
  }
  if (a.status === "blocked") {
    return "The policy engine denied this action, so it was blocked and never committed. This is the gate working.";
  }
  if (a.status === "applied") {
    if (a.historical) {
      const now = a.current_reason_code
        ? reasonText(a.current_reason_code)
        : "the agent is no longer authorized";
      return `The policy engine allowed this action at run time, so it was applied and recorded — before the agent's cert changed. The agent could NOT do this now: ${now}`;
    }
    return "The policy engine allowed this action, so it was applied and recorded in the auditable ledger.";
  }
  return "";
}

function OutcomePill({ status }: { status: string }) {
  // Blocked reads calm-good (a bad action was stopped); applied reads neutral-informational.
  const style =
    status === "blocked"
      ? "bg-success/15 text-success"
      : status === "reverted"
        ? "bg-info/15 text-info"
        : "bg-ink-600 text-ink-100";
  const tip =
    status === "blocked"
      ? "Denied by the policy engine — never committed to a real system."
      : status === "reverted"
        ? "Was applied, then reversed with a compensating entry."
        : "Allowed by the policy engine — committed and recorded in the ledger.";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${style}`} title={tip}>
      {status}
    </span>
  );
}

export function LedgerView({ runs }: { runs: LedgerRun[] }) {
  const [agent, setAgent] = useState("");
  const [decision, setDecision] = useState("");
  const [outcome, setOutcome] = useState("");
  const [q, setQ] = useState("");

  const agents = useMemo(
    () => Array.from(new Set(runs.flatMap((r) => r.actions.map((a) => a.agent_name)))).sort(),
    [runs],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return runs
      .map((r) => ({
        ...r,
        actions: r.actions.filter((a) => {
          if (agent && a.agent_name !== agent) return false;
          if (decision && a.decision !== decision) return false;
          if (outcome && a.status !== outcome) return false;
          if (
            needle &&
            !`${a.capability_label} ${a.action} ${a.agent_name} ${r.scenario_title ?? ""} ${r.scenario_id} ${r.run_id}`
              .toLowerCase()
              .includes(needle)
          )
            return false;
          return true;
        }),
      }))
      .filter((r) => r.actions.length > 0);
  }, [runs, agent, decision, outcome, q]);

  const select = "rounded border border-ink-500 bg-ink-800 px-2 py-1 text-xs text-ink-100";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search capability, agent, scenario, run…"
          className="min-w-[16rem] flex-1 rounded border border-ink-500 bg-ink-800 px-3 py-1.5 text-sm text-ink-50 placeholder:text-ink-400"
        />
        <select value={agent} onChange={(e) => setAgent(e.target.value)} className={select}>
          <option value="">All agents</option>
          {agents.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <select value={decision} onChange={(e) => setDecision(e.target.value)} className={select}>
          <option value="">All decisions</option>
          <option value="allow">Allow</option>
          <option value="deny">Deny</option>
        </select>
        <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className={select}>
          <option value="">All outcomes</option>
          <option value="applied">Applied</option>
          <option value="blocked">Blocked</option>
          <option value="reverted">Reverted</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No ledger entries match these filters.
        </div>
      ) : (
        filtered.map((run) => (
          <div key={run.run_id} className="overflow-hidden rounded-xl border border-ink-500">
            <div className="flex flex-wrap items-center justify-between gap-2 bg-ink-800 px-4 py-3">
              <div className="flex flex-col">
                <span className="text-sm font-semibold text-ink-50">
                  {run.scenario_title ?? run.scenario_id}
                </span>
                <span className="font-mono text-[11px] text-ink-400">{run.scenario_id}</span>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-ink-400">
                <span title="The run this action came from">
                  run{" "}
                  <Link
                    href={`/dashboard/runs/${run.run_id}`}
                    className="font-mono text-ink-200 hover:text-gold-300 hover:underline"
                  >
                    {run.run_id.slice(0, 10)}…
                  </Link>
                </span>
                <CopyButton value={run.run_id} label="copy run id" />
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-900/40 text-ink-300">
                  <tr>
                    <th className="px-4 py-2 font-medium">Action</th>
                    <th className="px-4 py-2 font-medium">Agent</th>
                    <th className="px-4 py-2 font-medium">PDP decision</th>
                    <th className="px-4 py-2 font-medium">Outcome</th>
                    <th className="px-4 py-2 font-medium">What this means</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {run.actions.map((a) => (
                    <tr key={a.action_id} className="align-top hover:bg-ink-800/60">
                      <td className="px-4 py-3">
                        <span className="text-gold-400" title={a.action}>
                          {a.capability_label}
                        </span>
                        <div className="font-mono text-[10px] text-ink-500">{a.action}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Link
                          href={`/dashboard/runs?agent=${a.agent}`}
                          title={a.agent}
                          className="text-ink-100 hover:text-gold-300 hover:underline"
                        >
                          {a.agent_name}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        {a.decision ? <DecisionPill decision={a.decision} /> : "—"}
                        {a.reason_code && (
                          <div className="mt-1 text-[10px] text-ink-400">{a.reason_code}</div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <OutcomePill status={a.status} />
                        {a.historical && (
                          <div
                            className="mt-1 inline-block rounded bg-warning/15 px-1.5 py-0.5 text-[10px] text-warning"
                            title="This action was recorded at run time; the agent's cert status has since changed, so this does NOT reflect current permissions."
                          >
                            historical — cert status has since changed
                          </div>
                        )}
                      </td>
                      <td className="max-w-md px-4 py-3 text-xs text-ink-200">
                        {whatThisMeans(a)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
