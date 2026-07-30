import { PageMeta } from "@/components/ui/PageMeta";
import { ontology, ventures, type OntologyGraph } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function OntologyPage() {
  let graphs: OntologyGraph[] = [];
  let error: string | null = null;
  try {
    const vs = await ventures.list();
    graphs = await Promise.all(vs.items.map((v) => ontology.graph(v.slug)));
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load ontology";
  }

  const nonEmpty = graphs.filter((g) => g.entities.length > 0);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Domain Ontology</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        Each venture&apos;s knowledge graph — the entities and typed relations that define its world.
        Scenarios are grounded in (and checked against) this model: relations can&apos;t dangle to
        unknown entities, and an entity no scenario ever references is flagged as an orphan (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load ontology: <code className="text-danger">{error}</code>
        </div>
      ) : nonEmpty.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          No ontology defined for any venture yet. Add entities via{" "}
          <code>POST /api/ontology/{"{venture}"}/entities</code> and relations via{" "}
          <code>.../relations</code>.
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {nonEmpty.map((g) => (
            <div key={g.venture} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="text-lg text-ink-50">{g.venture}</span>
                <span className="text-xs text-ink-400">
                  {g.entities.length} entities · {g.relations.length} relations
                </span>
                <span
                  className={`ml-auto rounded px-2 py-0.5 text-xs font-semibold ${
                    g.integrity.ok ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
                  }`}
                >
                  {g.integrity.ok ? "integrity ok" : `${g.integrity.dangling_relations.length} dangling`}
                </span>
                <span className="rounded bg-ink-700 px-2 py-0.5 text-xs text-ink-200">
                  {Math.round(g.grounding.grounded_pct * 100)}% grounded
                </span>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs uppercase tracking-wide text-ink-400">Entities</div>
                  <ul className="flex flex-wrap gap-1.5">
                    {g.entities.map((e) => {
                      const orphan = g.grounding.orphans.includes(e.name);
                      return (
                        <li
                          key={e.name}
                          title={orphan ? "No scenario references this entity" : e.description}
                          className={`rounded px-2 py-0.5 text-xs ${
                            orphan
                              ? "bg-warning/15 text-warning"
                              : "bg-ink-700 text-ink-100"
                          }`}
                        >
                          {e.name}
                          <span className="ml-1 text-[10px] text-ink-400">{e.category}</span>
                        </li>
                      );
                    })}
                  </ul>
                  {g.grounding.orphans.length > 0 && (
                    <p className="mt-2 text-[11px] text-warning">
                      Orphans (no scenario references): {g.grounding.orphans.join(", ")}
                    </p>
                  )}
                </div>

                <div>
                  <div className="mb-1 text-xs uppercase tracking-wide text-ink-400">Relations</div>
                  {g.relations.length > 0 ? (
                    <ul className="flex flex-col gap-1 text-sm">
                      {g.relations.map((r, i) => (
                        <li key={i} className="font-mono text-xs text-ink-200">
                          {r.from} <span className="text-gold-400">{r.relation}</span> {r.to}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-xs text-ink-500">No relations defined.</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
