import Link from "next/link";

import { api, type PackSummary } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function PacksPage() {
  let packs: PackSummary[] = [];
  let error: string | null = null;
  try {
    packs = (await api.packs()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load packs";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Certification Packs</h1>
      <p className="mb-8 text-ink-200">
        Scenario libraries that certify agents for a venture&apos;s Forge capabilities.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load packs: <code className="text-danger">{error}</code>
        </div>
      ) : packs.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No packs registered yet. Ingest one with{" "}
          <code>POST /api/packs {`{ "pack_dir": "greenstone/v1" }`}</code>.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {packs.map((p) => (
            <Link
              key={p.id}
              href={`/dashboard/packs/${p.packId}`}
              className="rounded-xl border border-ink-500 bg-ink-800 p-5 transition-colors hover:border-gold-600"
            >
              <div className="flex items-center justify-between">
                <span className="font-display text-xl text-gold-500">{p.name}</span>
                <span className="font-mono text-xs text-ink-300">v{p.version}</span>
              </div>
              <div className="mt-2 font-mono text-xs text-ink-300">{p.packId}</div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs">
                <span className="rounded bg-ink-600 px-2 py-0.5 text-ink-100">
                  {p.ownerVenture}
                </span>
                {p.phiRequired && (
                  <span className="rounded bg-danger/15 px-2 py-0.5 text-danger">PHI</span>
                )}
                <span className="rounded bg-ink-600 px-2 py-0.5 text-ink-100">
                  {p.executionModeDefault}
                </span>
                {p.signedBy && (
                  <span className="rounded bg-success/15 px-2 py-0.5 text-success">
                    signed
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
