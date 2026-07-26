import Link from "next/link";

import { VenturesExplorer } from "@/components/ventures/VenturesExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, ventures as venturesApi, type FlagCatalog, type Venture } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const EMPTY_CATALOG: FlagCatalog = { flags: {}, legend: {} };

export default async function VenturesPage() {
  let items: Venture[] = [];
  let catalog: FlagCatalog = EMPTY_CATALOG;
  let error: string | null = null;
  try {
    [items, catalog] = await Promise.all([
      venturesApi.list().then((r) => r.items),
      api.flagCatalog(),
    ]);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load ventures";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex items-start justify-between">
        <h1 className="text-3xl">Venture Registry</h1>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard/ventures/new"
            className="rounded bg-gold-500 px-3 py-1.5 text-sm font-semibold text-ink-900 hover:bg-gold-400"
          >
            + Add venture
          </Link>
          <PageMeta />
        </div>
      </div>
      <p className="mt-2 mb-6 max-w-prose text-ink-200">
        The ventures Green Companies operates. A venture is the target a Pack certifies agents for —
        each maps to compliance flags, internal Forges, and the capabilities it certifies against.
        This registry is the source of truth for the venture field across Packs, scenarios, and
        Lineage.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load ventures: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <VenturesExplorer ventures={items} catalog={catalog} />
      )}
    </div>
  );
}
