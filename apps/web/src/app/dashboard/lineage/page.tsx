import { LineageExplorer, type LineageEntity } from "@/components/lineage/LineageExplorer";
import { PageMeta } from "@/components/ui/PageMeta";
import { api, certs, governance } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function LineagePage({
  searchParams,
}: {
  searchParams: { root?: string };
}) {
  const entities: LineageEntity[] = [];
  let error: string | null = null;
  try {
    const [certList, agentList, packList, versions] = await Promise.all([
      certs.agent(),
      api.agents({ page_size: 500 }),
      api.packs(),
      governance.versions().catch(() => ({ versions: [] })),
    ]);
    const agentName = new Map(agentList.items.map((a) => [a.id, a.villageAgentId]));
    for (const c of certList.items) {
      entities.push({
        urn: `urn:gc:village:cert:${c.id}`,
        label: `${c.id.slice(0, 10)}… (${agentName.get(c.agentId) ?? "?"} · ${c.forgeCap})`,
        kind: "cert",
      });
    }
    for (const a of agentList.items) {
      entities.push({ urn: `urn:gc:village:agent:${a.villageAgentId}`, label: a.villageAgentId, kind: "agent" });
    }
    for (const p of packList.items) {
      entities.push({ urn: `urn:gc:village:pack:${p.packId}`, label: p.packId, kind: "pack" });
    }
    for (const v of versions.versions) {
      entities.push({ urn: `urn:gc:village:constitution:${v.version}`, label: v.version, kind: "constitution" });
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load lineage entities";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Lineage Explorer</h1>
        <PageMeta />
      </div>
      <p className="mb-6 text-ink-200">
        Provenance DAG between certs, agents, packs, constitution, and evidence. Pick any entity as
        the root, set depth, and use <em>incoming</em> to answer &ldquo;what points at this
        node&rdquo; (e.g. which certs pin a given constitution version).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">{error}</div>
      ) : entities.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No lineage entities yet — edges are emitted when a certificate is issued.
        </div>
      ) : (
        <LineageExplorer entities={entities} initialRoot={searchParams.root} />
      )}
    </div>
  );
}
