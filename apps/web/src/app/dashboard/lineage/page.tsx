import { certs, lineage, type LineageSubgraph } from "@/lib/api/client";

export const dynamic = "force-dynamic";

function shortUrn(urn: string): string {
  const parts = urn.split(":");
  return parts.length >= 5 ? `${parts[3]}:${parts.slice(4).join(":")}` : urn;
}

export default async function LineagePage() {
  let graph: LineageSubgraph | null = null;
  let rootUrn: string | null = null;
  let error: string | null = null;
  try {
    const certList = await certs.agent();
    if (certList.items.length > 0) {
      rootUrn = `urn:gc:village:cert:${certList.items[0].id}`;
      graph = await lineage.subgraph(rootUrn, 2);
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load lineage";
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl">Lineage Explorer</h1>
      <p className="mb-8 text-ink-200">
        Provenance edges between certs, agents, packs, constitution, and evidence.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
          {error}
        </div>
      ) : !graph || graph.edges.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No lineage yet — edges are emitted when a certificate is issued.
        </div>
      ) : (
        <div>
          <div className="mb-4 text-sm text-ink-300">
            Root: <span className="font-mono text-gold-400">{shortUrn(rootUrn!)}</span>
          </div>
          <div className="flex flex-col gap-2">
            {graph.edges.map((e, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-lg border border-ink-500 bg-ink-800 px-4 py-2 text-sm"
              >
                <span className="font-mono text-xs text-ink-100">{shortUrn(e.from)}</span>
                <span className="rounded bg-gold-600/20 px-2 py-0.5 text-xs text-gold-300">
                  {e.relation}
                </span>
                <span className="font-mono text-xs text-ink-100">→ {shortUrn(e.to)}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 text-xs text-ink-400">{graph.nodes.length} nodes in neighborhood</div>
        </div>
      )}
    </div>
  );
}
