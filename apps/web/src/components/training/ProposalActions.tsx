"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { approveProposal, rejectProposal } from "@/lib/api/client";

export function ProposalActions({ proposalId }: { proposalId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState<null | "approve" | "reject">(null);
  const [error, setError] = useState<string | null>(null);

  async function act(kind: "approve" | "reject") {
    const verb = kind === "approve" ? "approve (promotes prompt + re-certs)" : "reject";
    if (!confirm(`Really ${verb} this proposal?`)) return;
    setBusy(kind);
    setError(null);
    try {
      if (kind === "approve") await approveProposal(proposalId);
      else await rejectProposal(proposalId);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button
          onClick={() => act("approve")}
          disabled={busy !== null}
          className="rounded bg-success/20 px-3 py-1 text-xs font-semibold text-success transition-colors hover:bg-success/30 disabled:opacity-50"
        >
          {busy === "approve" ? "Approving…" : "Approve"}
        </button>
        <button
          onClick={() => act("reject")}
          disabled={busy !== null}
          className="rounded bg-danger/15 px-3 py-1 text-xs font-semibold text-danger transition-colors hover:bg-danger/25 disabled:opacity-50"
        >
          {busy === "reject" ? "Rejecting…" : "Reject"}
        </button>
      </div>
      {error && <span className="max-w-[14rem] text-[10px] text-danger">{error}</span>}
    </div>
  );
}
