import Link from "next/link";
import { notFound } from "next/navigation";

import { PageMeta } from "@/components/ui/PageMeta";
import { api, ventures as venturesApi, type FlagCatalog, type VentureDetail } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const STATUS_STYLE: Record<string, string> = {
  active: "bg-success/15 text-success",
  in_development: "bg-warning/20 text-warning",
  archived: "bg-ink-600 text-ink-300",
};
const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  in_development: "In development",
  archived: "Archived",
};
const EMPTY_CATALOG: FlagCatalog = { flags: {}, legend: {} };

export default async function VentureDetailPage({ params }: { params: { slug: string } }) {
  let v: VentureDetail;
  let catalog: FlagCatalog = EMPTY_CATALOG;
  try {
    [v, catalog] = await Promise.all([venturesApi.detail(params.slug), api.flagCatalog()]);
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-4xl">
      <Link href="/dashboard/ventures" className="text-sm text-ink-300 hover:text-ink-100">
        ← Venture Registry
      </Link>
      <div className="mt-2 flex items-start justify-between">
        <div>
          <h1 className="text-3xl">{v.name}</h1>
          <div className="mt-1 font-mono text-xs text-ink-400">{v.slug}</div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[v.status] ?? "bg-ink-600 text-ink-200"}`}
          >
            {STATUS_LABEL[v.status] ?? v.status}
          </span>
          <PageMeta />
        </div>
      </div>

      <p className="mt-4 text-ink-200">
        {v.description || <span className="text-ink-500">No description yet.</span>}
      </p>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        {v.defaultComplianceFlags.map((f) => {
          const info = catalog.flags[f];
          return (
            <span
              key={f}
              title={info?.tooltip}
              className={`cursor-help rounded px-2 py-0.5 ${
                info?.phi ? "bg-danger/15 text-danger" : "bg-ink-600 text-ink-100"
              }`}
            >
              {info?.label ?? f}
            </span>
          );
        })}
        {v.internalForges.map((fo) => (
          <span key={fo} className="rounded bg-info/15 px-2 py-0.5 text-info" title="Internal Forge / platform this venture runs on">
            {fo}
          </span>
        ))}
      </div>

      <section className="mt-8 grid gap-6 sm:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-200">
            Capabilities ({v.capabilities.length})
          </h2>
          {v.capabilities.length ? (
            <ul className="flex flex-wrap gap-1">
              {v.capabilities.map((c) => (
                <li key={c} className="rounded bg-ink-600 px-2 py-0.5 font-mono text-[11px] text-ink-100">
                  {c}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">
              None yet — the Forge capabilities this venture certifies against are populated by a
              spec upload or manual entry.
            </p>
          )}
        </div>
        <div>
          <h2 className="mb-2 text-sm font-semibold text-ink-200">Packs ({v.packs.length})</h2>
          {v.packs.length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {v.packs.map((p) => (
                <li key={p.packId}>
                  <Link href={`/dashboard/packs/${p.packId}`} className="text-gold-400 hover:underline">
                    {p.name}
                  </Link>{" "}
                  <span className="text-xs text-ink-400">
                    v{p.version} · {p.scenarioCount} scenarios
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-500">
              No packs yet.{" "}
              {v.committedScenarioCount > 0 ? (
                <Link href="/dashboard/packs/new" className="text-gold-400 hover:underline">
                  Create a pack →
                </Link>
              ) : (
                "Commit scenarios to this venture first (upload a spec or author in the Scenario Bank)."
              )}
            </p>
          )}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-2 text-sm font-semibold text-ink-200">Spec documents</h2>
        {v.specDocuments.length ? (
          <ul className="flex flex-col gap-1 text-sm text-ink-200">
            {v.specDocuments.map((d) => (
              <li key={d.id}>
                {d.filename} — {d.proposalsCount} proposals, {d.scenariosCount} draft scenarios
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-ink-500">
            No spec documents uploaded yet. Uploading a spec proposes venture metadata and draft
            scenarios for human review (coming in the spec-upload step).
          </p>
        )}
      </section>
    </div>
  );
}
