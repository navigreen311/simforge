import Link from "next/link";
import { notFound } from "next/navigation";

import { PageMeta } from "@/components/ui/PageMeta";
import { scenarioBank, type BankScenarioDetail } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const TIER_LABEL: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced_crisis: "Advanced-Crisis",
};

function Chips({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <span className="text-xs text-ink-500">{empty}</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((x) => (
        <span key={x} className="rounded bg-ink-600 px-2 py-0.5 font-mono text-[11px] text-ink-100">
          {x}
        </span>
      ))}
    </div>
  );
}

export default async function BankScenarioDetailPage({
  params,
}: {
  params: { publicId: string };
}) {
  let s: BankScenarioDetail;
  try {
    s = await scenarioBank.detail(params.publicId);
  } catch {
    notFound();
  }

  const lineageUrn = s.scenarioId
    ? `urn:gc:village:scenario:${s.scenarioId}`
    : `urn:gc:village:bankscenario:${s.publicId}`;

  return (
    <div className="mx-auto max-w-4xl">
      <Link href="/dashboard/scenario-bank" className="text-sm text-ink-300 hover:text-ink-100">
        ← Scenario Bank
      </Link>
      <div className="mt-2 flex items-start justify-between">
        <div>
          <h1 className="text-2xl text-ink-50">{s.title}</h1>
          <div className="mt-1 font-mono text-xs text-ink-400">{s.scenarioId ?? s.publicId}</div>
        </div>
        <PageMeta />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="capitalize rounded bg-ink-600 px-2 py-0.5 text-ink-100">{s.pack}</span>
        <span className="rounded bg-ink-600 px-2 py-0.5 font-mono text-ink-300">{s.family}</span>
        <span className="rounded bg-ink-600 px-2 py-0.5 text-ink-200">
          {TIER_LABEL[s.tier] ?? s.tier}
        </span>
        <span
          className={`rounded px-2 py-0.5 font-semibold ${
            s.status === "committed"
              ? "bg-success/15 text-success"
              : s.status === "draft"
                ? "bg-warning/20 text-warning"
                : "bg-ink-600 text-ink-200"
          }`}
        >
          {s.status}
        </span>
        {s.aiDrafted && (
          <span className="rounded bg-info/20 px-2 py-0.5 text-info">
            AI-drafted · unverified until a human approves
          </span>
        )}
      </div>

      <section className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-ink-200">Situation</h2>
        <p className="whitespace-pre-wrap rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-100">
          {s.situation || "—"}
        </p>
      </section>

      <section className="mt-6 grid gap-6 sm:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-200">Expected behaviors</h2>
          {s.expectedBehaviors.length ? (
            <ul className="list-disc pl-5 text-sm text-ink-100">
              {s.expectedBehaviors.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          ) : (
            <span className="text-xs text-ink-500">none recorded</span>
          )}
        </div>
        <div className="flex flex-col gap-4">
          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink-200">Adversarial tactics</h2>
            <Chips items={s.adversarialTactics} empty="none" />
          </div>
          <div>
            <h2 className="mb-2 text-sm font-semibold text-ink-200">Jurisdiction flags</h2>
            <Chips items={s.jurisdictionFlags} empty="none" />
          </div>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="mb-2 text-sm font-semibold text-ink-200">Provenance</h2>
        <dl className="grid grid-cols-2 gap-2 rounded-lg border border-ink-500 bg-ink-800 p-4 text-xs">
          <Row k="Source" v={s.sourceType} />
          <Row k="Reference" v={s.sourceRef ?? "—"} />
          <Row k="Created by" v={s.createdBy} />
          <Row k="Created" v={new Date(s.createdAt).toLocaleString()} />
          <Row k="Reviewed by" v={s.reviewedBy ?? "—"} />
          <Row k="Version" v={String(s.version)} />
          <Row k="Lineage" v={<Link href={`/dashboard/lineage?root=${lineageUrn}`} className="text-gold-400 hover:underline">view provenance chain →</Link>} />
        </dl>
        {s.sourceExcerpt && (
          <div className="mt-3">
            <h3 className="mb-1 text-xs text-ink-400">Source excerpt</h3>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-ink-600 bg-ink-900 p-3 text-[11px] text-ink-300">
              {s.sourceExcerpt}
            </pre>
          </div>
        )}
      </section>

      {s.status !== "committed" && (
        <p className="mt-6 rounded-lg border border-ink-600 bg-ink-800 p-3 text-xs text-ink-400">
          Draft review actions (Edit / Approve / Reject / Commit) are wired in the ingestion +
          promotion flow. Committing is an explicit, logged human action — nothing here auto-commits.
        </p>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-ink-400">{k}</dt>
      <dd className="text-ink-100">{v}</dd>
    </div>
  );
}
