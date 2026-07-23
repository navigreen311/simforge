import { GapsExplorer } from "@/components/gaps/GapsExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { gaps, type SoftwareGap } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function SoftwareGapsPage() {
  let items: SoftwareGap[] = [];
  let error: string | null = null;
  try {
    items = (await gaps.software()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load gaps";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Software Gaps</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Forge defects surfaced by scenario runs (routed to Linear in staging/prod). Filter, search,
        sort, and cluster likely duplicates.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load gaps: <code className="text-danger">{error}</code>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No software gaps yet. Run an advanced-crisis scenario to surface Forge friction.
        </div>
      ) : (
        <GapsExplorer gaps={items} />
      )}
    </div>
  );
}
