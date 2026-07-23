import Link from "next/link";

import { CopyButton } from "@/components/ui/CopyButton";
import { PageMeta } from "@/components/ui/PageMeta";
import {
  drift,
  governance,
  type AmendmentFull,
  type ConstitutionContent,
  type ConstitutionDriftReport,
  type ConstitutionVersion,
} from "@/lib/api/client";

export const dynamic = "force-dynamic";

const STATUS_STYLE: Record<string, string> = {
  proposed: "bg-info/15 text-info",
  in_cooling: "bg-warning/20 text-warning",
  ratified: "bg-success/15 text-success",
  withdrawn: "bg-ink-600 text-ink-300",
  vetoed: "bg-danger/15 text-danger",
};

function coolingRemaining(iso: string): string {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "eligible to ratify";
  const days = Math.floor(ms / 86_400_000);
  const hrs = Math.floor((ms % 86_400_000) / 3_600_000);
  return `${days}d ${hrs}h remaining`;
}

export default async function ConstitutionPage() {
  let versions: ConstitutionVersion[] = [];
  let active: ConstitutionContent | null = null;
  let amendments: AmendmentFull[] = [];
  let cdrift: ConstitutionDriftReport | null = null;
  let error: string | null = null;

  try {
    const [vs, hist, cd] = await Promise.all([
      governance.versions(),
      governance.history(),
      drift.constitution(),
    ]);
    versions = vs.versions;
    amendments = hist.amendments;
    cdrift = cd;
    const activeVersion = versions.find((v) => v.active);
    if (activeVersion) active = await governance.version(activeVersion.version);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load constitution";
  }

  const stalePins = cdrift ? cdrift.stale_certs : 0;

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Constitution</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        The governing document for agent certification and autonomy. Amendments require a cooling
        period + Ivan ratification.
      </p>

      {error && (
        <div className="mb-6 rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          {error}
        </div>
      )}

      {/* Stale-pin callout (P0-B Finding 2). */}
      {stalePins > 0 && cdrift && (
        <div className="mb-6 rounded-xl border border-danger/50 bg-danger/15 p-4 text-sm text-ink-50">
          <strong className="text-danger">⚠ {stalePins} cert(s) pinned to a superseded constitution.</strong>{" "}
          The active version is <span className="font-mono">{cdrift.current_constitution}</span> but{" "}
          {stalePins} cert(s) are pinned to an older version.{" "}
          <Link href="/dashboard/drift" className="text-gold-400 hover:underline">
            view drift detail →
          </Link>
        </div>
      )}

      {/* Version history */}
      {versions.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-xl">Version history</h2>
          <div className="flex flex-col gap-2">
            {versions.map((v) => (
              <div
                key={v.version}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-sm"
              >
                <span className="font-display text-lg text-gold-500">{v.version}</span>
                {v.active ? (
                  <span className="rounded bg-success/15 px-2 py-0.5 text-xs text-success">active</span>
                ) : (
                  <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-300">
                    superseded by {v.superseded_by}
                  </span>
                )}
                <span className="text-xs text-ink-300">
                  ratified {new Date(v.ratified_at).toLocaleDateString()} by {v.ratified_by}
                </span>
                <span className="ml-auto flex items-center gap-2 font-mono text-[10px] text-ink-400">
                  {v.content_hash.slice(0, 20)}…
                  <CopyButton value={v.content_hash} label="copy hash" />
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Active constitution TEXT — the highest-priority item on this page. */}
      {active ? (
        <section className="mb-8">
          <h2 className="mb-3 text-xl">
            Active text — <span className="font-mono text-gold-400">{active.version}</span>
          </h2>
          <pre className="max-h-[28rem] overflow-auto rounded-xl border border-ink-500 bg-ink-900 p-4 text-xs leading-relaxed text-ink-100">
            {active.yaml}
          </pre>
        </section>
      ) : (
        !error && (
          <div className="mb-8 rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
            No constitution ratified yet. Seed it with{" "}
            <code>python scripts/seed-constitution.py</code>.
          </div>
        )
      )}

      {/* Amendments — full bodies + cooling timers */}
      <section>
        <h2 className="mb-3 text-xl">Amendments</h2>
        {amendments.length === 0 ? (
          <p className="text-ink-300">No amendments proposed.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {amendments.map((a) => (
              <div key={a.amendment_id} className="rounded-xl border border-ink-500 bg-ink-800 p-4">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[a.status] ?? "bg-ink-600"}`}>
                    {a.status}
                  </span>
                  <span className="font-mono text-xs text-ink-300">{a.amendment_id}</span>
                  <span className="text-ink-300">by {a.proposed_by}</span>
                  {a.status !== "ratified" && a.status !== "vetoed" && a.status !== "withdrawn" && (
                    <span className="ml-auto text-xs text-warning">
                      cooling: {coolingRemaining(a.cooling_ends_at)}
                    </span>
                  )}
                  {a.ratified_at && (
                    <span className="ml-auto text-xs text-ink-400">
                      ratified {new Date(a.ratified_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                {a.diff_yaml && (
                  <pre className="mt-3 max-h-40 overflow-auto rounded border border-ink-600 bg-ink-900 p-3 text-[11px] text-ink-200">
                    {a.diff_yaml}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
