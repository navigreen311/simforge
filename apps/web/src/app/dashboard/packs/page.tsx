import Link from "next/link";

import { PacksExplorer } from "@/components/packs/PacksExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, type FlagCatalog, type PackCard } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const EMPTY_CATALOG: FlagCatalog = { flags: {}, legend: {} };

export default async function PacksPage() {
  let packs: PackCard[] = [];
  let catalog: FlagCatalog = EMPTY_CATALOG;
  let error: string | null = null;
  try {
    [packs, catalog] = await Promise.all([
      api.packs().then((r) => r.items),
      api.flagCatalog(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load packs";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Certification Packs</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/packs/new"
            className="rounded bg-gold-500 px-3 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400"
          >
            + New Pack
          </Link>
          <PageMeta />
        </div>
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        A Pack is the set of scenarios an agent must pass to be certified for one venture&apos;s
        work. Each Pack maps to a venture and the compliance flags that venture must satisfy.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load packs: <code className="text-danger">{error}</code>
        </div>
      ) : packs.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No packs registered yet.
        </div>
      ) : (
        <PacksExplorer packs={packs} catalog={catalog} />
      )}
    </div>
  );
}
