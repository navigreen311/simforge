"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { approveProposal, rejectProposal, type ConsequenceCert } from "@/lib/api/client";

// Human-gated approve/reject. Approval shows the blast-radius preview and needs explicit
// confirmation; rejection asks for an optional reason. Nothing is applied without the human here.
export function ProposalActions({
  proposalId,
  agentName,
  fromVersion,
  toVersion,
  wouldSuspend,
}: {
  proposalId: string;
  agentName: string;
  fromVersion: string;
  toVersion: string;
  wouldSuspend: ConsequenceCert[];
}) {
  const router = useRouter();
  const [mode, setMode] = useState<null | "approve" | "reject">(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function confirm(kind: "approve" | "reject") {
    setBusy(true);
    setError(null);
    try {
      if (kind === "approve") await approveProposal(proposalId);
      else await rejectProposal(proposalId, reason);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
      setBusy(false);
    }
  }

  if (mode === null) {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="flex gap-2">
          <button
            onClick={() => setMode("approve")}
            className="rounded bg-success/20 px-3 py-1 text-xs font-semibold text-success hover:bg-success/30"
          >
            Approve
          </button>
          <button
            onClick={() => setMode("reject")}
            className="rounded bg-danger/15 px-3 py-1 text-xs font-semibold text-danger hover:bg-danger/25"
          >
            Reject
          </button>
        </div>
        {error && <span className="max-w-[16rem] text-[10px] text-danger">{error}</span>}
      </div>
    );
  }

  if (mode === "approve") {
    return (
      <div className="w-full rounded-lg border border-success/40 bg-success/5 p-3 text-sm">
        <p className="text-ink-100">
          Approve will promote <strong>{agentName}</strong>&apos;s prompt {fromVersion} →{" "}
          {toVersion} and <strong>suspend {wouldSuspend.length} certificate
          {wouldSuspend.length === 1 ? "" : "s"}</strong> pinned to {fromVersion} for
          re-certification:
        </p>
        {wouldSuspend.length > 0 && (
          <ul className="mt-1 flex flex-wrap gap-1">
            {wouldSuspend.map((c) => (
              <li key={c.cap} className="rounded bg-danger/10 px-2 py-0.5 text-[11px] text-danger" title={c.cap}>
                {c.label}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => confirm("approve")}
            disabled={busy}
            className="rounded bg-success/25 px-3 py-1 text-xs font-semibold text-success hover:bg-success/35 disabled:opacity-50"
          >
            {busy ? "Approving…" : `Confirm — promote + suspend ${wouldSuspend.length}`}
          </button>
          <button onClick={() => setMode(null)} disabled={busy} className="rounded border border-ink-500 px-3 py-1 text-xs text-ink-200 hover:bg-ink-700">
            Cancel
          </button>
        </div>
        {error && <p className="mt-1 text-[10px] text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <div className="w-full rounded-lg border border-ink-500 bg-ink-900/40 p-3 text-sm">
      <label className="text-xs text-ink-200">Reject this proposal — optional reason:</label>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
        placeholder="Why is this proposal being rejected?"
        className="mt-1 w-full rounded border border-ink-500 bg-ink-800 px-2 py-1 text-xs text-ink-50"
      />
      <div className="mt-2 flex gap-2">
        <button
          onClick={() => confirm("reject")}
          disabled={busy}
          className="rounded bg-danger/20 px-3 py-1 text-xs font-semibold text-danger hover:bg-danger/30 disabled:opacity-50"
        >
          {busy ? "Rejecting…" : "Confirm reject"}
        </button>
        <button onClick={() => setMode(null)} disabled={busy} className="rounded border border-ink-500 px-3 py-1 text-xs text-ink-200 hover:bg-ink-700">
          Cancel
        </button>
      </div>
      {error && <p className="mt-1 text-[10px] text-danger">{error}</p>}
    </div>
  );
}
