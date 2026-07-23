"use client";

import { StatusDot } from "@/components/common/StatusDot";
import { TierPill } from "@/components/common/TierPill";
import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type { AgentCert } from "@/lib/api/client";

const STATUSES = ["active", "suspended", "revoked", "expired"];
const TIERS = ["foundational", "intermediate", "advanced_crisis"];

export function CertsExplorer({
  certs,
  nameById,
}: {
  certs: AgentCert[];
  nameById: Record<string, string>;
}) {
  const forges = Array.from(new Set(certs.map((c) => c.forgeCap.split(".")[0]))).sort();

  const columns: Column<AgentCert>[] = [
    {
      key: "agent",
      header: "Agent",
      sortValue: (c) => nameById[c.agentId] ?? c.agentId,
      searchText: (c) => nameById[c.agentId] ?? c.agentId,
      cell: (c) => (
        <span className="font-mono text-xs text-ink-100">{nameById[c.agentId] ?? c.agentId}</span>
      ),
    },
    {
      key: "cap",
      header: "Forge capability",
      sortValue: (c) => c.forgeCap,
      searchText: (c) => `${c.forgeCap} ${c.id}`,
      filter: {
        label: "Forge",
        options: forges.map((f) => ({ label: f, value: f })),
        match: (c, v) => c.forgeCap.startsWith(`${v}.`),
      },
      cell: (c) => <span className="font-mono text-xs text-gold-400">{c.forgeCap}</span>,
    },
    {
      key: "tier",
      header: "Tier",
      sortValue: (c) => c.tier,
      filter: {
        label: "Tier",
        options: TIERS.map((t) => ({ label: t, value: t })),
        match: (c, v) => c.tier === v,
      },
      cell: (c) => <TierPill tier={c.tier} />,
    },
    {
      key: "status",
      header: "Status",
      sortValue: (c) => c.status,
      filter: {
        label: "Status",
        options: STATUSES.map((s) => ({ label: s, value: s })),
        match: (c, v) => c.status === v,
      },
      cell: (c) => <StatusDot status={c.status} label={c.status} />,
    },
    {
      key: "reason",
      header: "Reason",
      cell: (c) => (
        <span className="text-xs text-ink-300">{c.revocationReason ?? "—"}</span>
      ),
    },
    {
      key: "issued",
      header: "Issued",
      sortValue: (c) => c.issuedAt,
      cell: (c) => (
        <span className="text-xs text-ink-200">
          {c.issuedAt ? new Date(c.issuedAt).toLocaleDateString() : "—"}
        </span>
      ),
    },
    {
      key: "expires",
      header: "Expires",
      sortValue: (c) => c.expiresAt,
      cell: (c) => (
        <span className="text-xs text-ink-200">
          {c.expiresAt ? new Date(c.expiresAt).toLocaleDateString() : "—"}
        </span>
      ),
    },
    {
      key: "snapshot",
      header: "Snapshot",
      cell: (c) => (
        <span className="font-mono text-[10px] text-ink-400" title={c.certSnapshotId}>
          {c.certSnapshotId.slice(0, 10)}…
        </span>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={certs}
      getRowKey={(c) => c.id}
      searchPlaceholder="Search agent / cap / cert id…"
      emptyState={
        <EmptyState
          title="No certificates match"
          description="Adjust the status/tier/forge filters, or issue a cert from a passing battery."
          icon="📜"
        />
      }
    />
  );
}
