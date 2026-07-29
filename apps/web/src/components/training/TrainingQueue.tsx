"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { CopyButton } from "@/components/ui/CopyButton";
import { ProposalActions } from "@/components/training/ProposalActions";
import { type EnrichedProposal } from "@/lib/api/client";
import { describeDimension } from "@/lib/dimensions";

const STATUS_STYLE: Record<string, string> = {
  proposed: "bg-warning/20 text-warning",
  approved: "bg-success/15 text-success",
  rejected: "bg-ink-600 text-ink-300",
};

function statusLabel(s: string): string {
  return s === "proposed" ? "pending" : s;
}

function Card({ p }: { p: EnrichedProposal }) {
  const c = p.consequence;
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <div className="flex flex-wrap items-center gap-3">
        {p.agent_village_id ? (
          <Link href={`/dashboard/runs?agent=${p.agent_village_id}`} className="text-sm font-semibold text-ink-50 hover:text-gold-300 hover:underline" title={p.agent_village_id}>
            {p.agent_name ?? p.agent_village_id}
          </Link>
        ) : (
          <span className="text-sm font-semibold text-ink-50">{p.agent_name ?? p.agent_id}</span>
        )}
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[p.status] ?? "bg-ink-600"}`}>
          {statusLabel(p.status)}
        </span>
        <span
          className="cursor-help font-mono text-xs text-ink-300 underline decoration-ink-500 decoration-dotted underline-offset-4"
          title="The agent's instruction set was upgraded from the old version to the new one."
        >
          {p.current_prompt_version} → {p.proposed_prompt_version}
        </span>
        {p.reviewed_by && p.status !== "proposed" && (
          <span className="text-xs text-ink-400">
            reviewed by {p.reviewed_by}
            {p.reviewed_at ? ` · ${new Date(p.reviewed_at).toLocaleDateString()}` : ""}
          </span>
        )}
      </div>

      {/* Weak dimensions — plain names from the shared source. */}
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-ink-400">Weak on:</span>
        {p.weak_dims.map((d) => {
          const info = describeDimension(d);
          return (
            <span key={d} className="rounded bg-danger/10 px-2 py-0.5 text-danger" title={`${info.tip} (${d})`}>
              {info.name} <span className="font-mono text-[10px] text-danger/70">{d}</span>
            </span>
          );
        })}
      </div>

      {/* Triggering run */}
      {(p.scenario_title || p.run_hash) && (
        <p className="mt-2 text-xs text-ink-300">
          Triggered by run:{" "}
          {p.run_hash ? (
            <Link href={`/dashboard/runs/${p.run_hash}`} className="text-gold-400 hover:underline">
              {p.scenario_title ?? p.scenario_id ?? p.run_hash}
            </Link>
          ) : (
            <span>{p.scenario_title}</span>
          )}
          {p.run_hash && (
            <span className="ml-2 inline-flex items-center gap-1 font-mono text-[10px] text-ink-500">
              {p.run_hash.slice(0, 10)}… <CopyButton value={p.run_hash} label="copy" />
            </span>
          )}
        </p>
      )}

      {/* Proposed change — the heart of it, prominent. */}
      <div className="mt-3 rounded-lg border border-gold-600/40 bg-gold-600/5 p-3">
        <div className="text-xs font-semibold text-gold-300">Proposed change to the agent&apos;s prompt</div>
        <p className="mt-1 whitespace-pre-line text-sm text-ink-100">{p.proposed_refinement}</p>
        <p className="mt-2 text-[11px] text-ink-400">{p.rationale}</p>
      </div>

      {/* Consequence */}
      {c.kind === "applied" && (
        <div className="mt-3 rounded-lg border border-danger/30 bg-danger/5 p-3 text-sm">
          <div className="text-ink-100">
            Prompt promoted {p.current_prompt_version} → {p.proposed_prompt_version}
            {c.promoted_on ? ` on ${new Date(c.promoted_on).toLocaleDateString()}` : ""}.
          </div>
          <div className="mt-1 text-ink-100">
            Certificates suspended for re-certification: <strong>{c.certs.length}</strong>
            {c.inferred && <span className="ml-1 text-[10px] text-ink-400">(inferred from lifecycle events)</span>}
          </div>
          {c.certs.length > 0 && (
            <ul className="mt-1 flex flex-wrap gap-1">
              {c.certs.map((x) => (
                <li key={x.cap} className="rounded bg-danger/10 px-2 py-0.5 text-[11px] text-danger" title={x.cap}>
                  {x.label}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-ink-200">
            Re-certification required: <strong>{p.agent_name ?? p.agent_village_id}</strong> must
            pass certification on {p.proposed_prompt_version} to restore these capabilities.{" "}
            <Link href="/dashboard/certs" className="text-gold-400 hover:underline">
              View certifications
            </Link>
            .
          </p>
        </div>
      )}
      {c.kind === "preview" && (
        <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-ink-100">
          Approving will promote {p.current_prompt_version} → {p.proposed_prompt_version} and{" "}
          <strong>suspend {c.certs.length} cert{c.certs.length === 1 ? "" : "s"}</strong> pinned to{" "}
          {p.current_prompt_version} for re-certification
          {c.certs.length > 0 && (
            <>
              :{" "}
              <span className="inline-flex flex-wrap gap-1 align-middle">
                {c.certs.map((x) => (
                  <span key={x.cap} className="rounded bg-danger/10 px-2 py-0.5 text-[11px] text-danger" title={x.cap}>
                    {x.label}
                  </span>
                ))}
              </span>
            </>
          )}
          .
        </div>
      )}

      {p.status === "proposed" && (
        <div className="mt-3">
          <ProposalActions
            proposalId={p.id}
            agentName={p.agent_name ?? p.agent_village_id ?? "the agent"}
            fromVersion={p.current_prompt_version}
            toVersion={p.proposed_prompt_version}
            wouldSuspend={c.certs}
          />
        </div>
      )}
    </div>
  );
}

export function TrainingQueue({ proposals }: { proposals: EnrichedProposal[] }) {
  const [statusFilter, setStatusFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [q, setQ] = useState("");

  const agents = useMemo(
    () => Array.from(new Set(proposals.map((p) => p.agent_name ?? p.agent_village_id ?? p.agent_id))).sort(),
    [proposals],
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return proposals.filter((p) => {
      if (statusFilter && p.status !== statusFilter) return false;
      const who = p.agent_name ?? p.agent_village_id ?? p.agent_id;
      if (agentFilter && who !== agentFilter) return false;
      if (
        needle &&
        !`${who} ${p.weak_dims.join(" ")} ${p.scenario_title ?? ""} ${p.proposed_refinement}`
          .toLowerCase()
          .includes(needle)
      )
        return false;
      return true;
    });
  }, [proposals, statusFilter, agentFilter, q]);

  const pending = filtered.filter((p) => p.status === "proposed");
  const rest = filtered.filter((p) => p.status !== "proposed");
  const select = "rounded border border-ink-500 bg-ink-800 px-2 py-1 text-xs text-ink-100";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search agent, dimension, scenario, change…"
          className="min-w-[16rem] flex-1 rounded border border-ink-500 bg-ink-800 px-3 py-1.5 text-sm text-ink-50 placeholder:text-ink-400"
        />
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className={select}>
          <option value="">All statuses</option>
          <option value="proposed">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <select value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} className={select}>
          <option value="">All agents</option>
          {agents.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>

      {/* Pending queue — the human's work, first. */}
      <div className="flex items-center gap-2">
        <h2 className="text-lg">Awaiting review</h2>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${pending.length > 0 ? "bg-warning/20 text-warning" : "bg-ink-600 text-ink-300"}`}>
          {pending.length} proposal{pending.length === 1 ? "" : "s"} awaiting review
        </span>
      </div>
      {pending.length === 0 ? (
        <p className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          Nothing awaiting review.
        </p>
      ) : (
        pending.map((p) => <Card key={p.id} p={p} />)
      )}

      {rest.length > 0 && (
        <>
          <h2 className="mt-2 text-lg">Reviewed</h2>
          {rest.map((p) => (
            <Card key={p.id} p={p} />
          ))}
        </>
      )}
    </div>
  );
}
