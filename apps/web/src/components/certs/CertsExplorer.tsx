"use client";

import { CopyButton } from "@/components/ui/CopyButton";
import { StatusDot } from "@/components/common/StatusDot";
import { TierPill } from "@/components/common/TierPill";
import { Column, DataTable } from "@/components/ui/DataTable";
import { EmptyState } from "@/components/ui/EmptyState";
import type { AgentCert } from "@/lib/api/client";

const STATUSES = ["active", "suspended", "revoked", "expired"];
const TIERS = ["foundational", "intermediate", "advanced_crisis"];

// What each status MEANS for the agent (shown on hover + in the summary).
const STATUS_MEANING: Record<string, string> = {
  active: "This agent is currently certified for this capability.",
  suspended:
    "Temporarily not certified — the cert exists but is paused. The agent should not perform this capability until it's active again.",
  revoked:
    "Permanently withdrawn — this cert no longer certifies the agent. A new certification would be required.",
  expired: "Past its expiry date — no longer valid until renewed.",
};

// Plain-language expansion of revocation reasons.
const REASON_LABEL: Record<string, string> = {
  demo: "Seed/demo data — not a real revocation.",
  "demo revocation": "Seed/demo data — not a real revocation.",
};

function reasonText(reason: string | null): string {
  if (!reason || !reason.trim()) return "No reason recorded.";
  const key = reason.trim().toLowerCase();
  if (REASON_LABEL[key]) return REASON_LABEL[key];
  // Humanize an unknown code rather than leaving it bare.
  return reason.charAt(0).toUpperCase() + reason.slice(1);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function isDemo(c: AgentCert): boolean {
  return (
    /\.demo\./.test(c.forgeCap) ||
    ["demo", "demo revocation"].includes((c.revocationReason ?? "").trim().toLowerCase())
  );
}

export function CertsExplorer({
  certs,
  nameById,
}: {
  certs: AgentCert[];
  nameById: Record<string, string>;
}) {
  const forges = Array.from(new Set(certs.map((c) => c.capabilityForge || c.forgeCap.split(".")[0]))).sort();
  const agentName = (c: AgentCert) => nameById[c.agentId] ?? c.agentId;

  const columns: Column<AgentCert>[] = [
    {
      key: "agent",
      header: "Agent",
      sortValue: agentName,
      searchText: agentName,
      cell: (c) => <span className="font-mono text-xs text-ink-100">{agentName(c)}</span>,
    },
    {
      key: "cap",
      header: "Forge capability",
      sortValue: (c) => c.capabilityLabel || c.forgeCap,
      searchText: (c) => `${c.capabilityLabel} ${c.capabilityDescription} ${c.forgeCap} ${c.id}`,
      filter: {
        label: "Forge",
        options: forges.map((f) => ({ label: f, value: f })),
        match: (c, v) => c.forgeCap.startsWith(`${v}.`),
      },
      cell: (c) => (
        <div className="min-w-[220px]">
          <div className="text-sm text-ink-50" title={c.capabilityDescription || undefined}>
            {c.capabilityLabel || c.forgeCap}
          </div>
          <div className="font-mono text-[10px] text-ink-400">{c.forgeCap}</div>
        </div>
      ),
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
      cell: (c) => (
        <span title={STATUS_MEANING[c.status] ?? c.status} className="cursor-help">
          <StatusDot status={c.status} label={c.status} />
        </span>
      ),
    },
    {
      key: "reason",
      header: "Reason",
      searchText: (c) => reasonText(c.revocationReason),
      cell: (c) => (
        <span
          className={`text-xs ${c.revocationReason ? "text-ink-200" : "text-ink-500 italic"}`}
        >
          {reasonText(c.revocationReason)}
        </span>
      ),
    },
    {
      key: "issued",
      header: "Issued",
      align: "right",
      sortValue: (c) => c.issuedAt,
      cell: (c) => <span className="text-xs text-ink-200">{fmtDate(c.issuedAt)}</span>,
    },
    {
      key: "expires",
      header: "Expires",
      align: "right",
      sortValue: (c) => c.expiresAt,
      cell: (c) => {
        const past = c.expiresAt && new Date(c.expiresAt) < new Date();
        return (
          <span
            className={`text-xs ${past ? "font-semibold text-danger" : "text-ink-200"}`}
            title={past ? "This certificate's expiry date is in the past." : undefined}
          >
            {fmtDate(c.expiresAt)}
            {past && " ⚠"}
          </span>
        );
      },
    },
    {
      key: "snapshot",
      header: "Snapshot",
      cell: (c) => (
        <span className="inline-flex items-center gap-1">
          <a
            href={`/dashboard/lineage?root=urn:gc:village:cert:${c.id}`}
            className="font-mono text-[10px] text-gold-400 hover:underline"
            title="Cryptographic snapshot of this certificate at issue — the tamper-evident proof of what was certified. Opens its Lineage."
          >
            {c.certSnapshotId.slice(0, 10)}…
          </a>
          <CopyButton value={c.certSnapshotId} label="copy" />
        </span>
      ),
    },
  ];

  return (
    <div>
      <CertSummary certs={certs} agentName={agentName} />
      <DataTable
        columns={columns}
        data={certs}
        getRowKey={(c) => c.id}
        searchPlaceholder="Search agent / capability / cert id…"
        emptyState={
          <EmptyState
            title="No certificates match"
            description="Adjust the status/tier/forge filters, or issue a cert from a passing battery."
            icon="📜"
          />
        }
      />
    </div>
  );
}

function CertSummary({
  certs,
  agentName,
}: {
  certs: AgentCert[];
  agentName: (c: AgentCert) => string;
}) {
  const total = certs.length;
  const by = (s: string) => certs.filter((c) => c.status === s).length;
  const active = by("active");
  const agents = Array.from(new Set(certs.map(agentName)));
  const demo = certs.filter(isDemo).length;

  const noActive = active === 0 && total > 0;
  const singleAgent = agents.length === 1 && total > 0;
  const demoHeavy = total > 0 && demo > total / 2;
  const warn = noActive || singleAgent || demoHeavy;

  return (
    <div
      className={`mb-5 rounded-xl border p-4 text-sm ${
        warn ? "border-warning/50 bg-warning/10" : "border-success/40 bg-success/10"
      }`}
    >
      {noActive ? (
        <p className="font-semibold text-warning">
          No agent currently holds an ACTIVE certification. All {total} certificates in the registry
          are suspended or revoked. Under the readiness policy, no agent should be operating above
          minimum autonomy until active certifications are issued.
        </p>
      ) : (
        <p className="font-semibold text-success">
          {active} of {total} certificate{total === 1 ? "" : "s"} are active.
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        <span className="text-success">{active} active</span>
        <span className="text-warning">{by("suspended")} suspended</span>
        <span className="text-danger">{by("revoked")} revoked</span>
        <span className="text-ink-300">{by("expired")} expired</span>
        {demo > 0 && <span className="text-ink-400">· {demo} seed/demo</span>}
      </div>

      {singleAgent && (
        <p className="mt-2 text-xs text-ink-200">
          All {total} certificates belong to a single agent ({agents[0]}). The registry does not yet
          cover the rest of the roster.
        </p>
      )}
      {demoHeavy && (
        <p className="mt-1 text-xs text-ink-200">
          Most entries are seed/demo certificates, not production certifications.
        </p>
      )}
    </div>
  );
}
