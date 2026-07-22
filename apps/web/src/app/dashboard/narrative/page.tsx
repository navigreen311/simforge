import { api, narrative, type NarrativeArc } from "@/lib/api/client";

export const dynamic = "force-dynamic";

function RepDelta({ v }: { v: number }) {
  const cls = v > 0 ? "text-success" : v < 0 ? "text-danger" : "text-ink-300";
  const sign = v > 0 ? "+" : "";
  return (
    <span className={`font-mono text-xs ${cls}`}>
      {sign}
      {v.toFixed(3)}
    </span>
  );
}

export default async function NarrativePage() {
  let arcs: NarrativeArc[] = [];
  let error: string | null = null;
  try {
    const agents = await api.agents({ page_size: 200 });
    arcs = (
      await Promise.all(
        agents.items.map(async (a) => {
          try {
            return await narrative.arc(a.villageAgentId);
          } catch {
            return null;
          }
        }),
      )
    ).filter((a): a is NarrativeArc => a !== null && a.arc_length > 0);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load narrative arcs";
  }

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-1 text-3xl">Narrative</h1>
      <p className="mb-8 text-ink-200">
        Integrated-narrative runs accrete story beats into an agent&apos;s arc — how its character held
        and which way its standing moved. Effects are recorded SimForge-side; VillageData is never
        written (ADR-0035).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load narrative arcs: <code className="text-danger">{error}</code>
        </div>
      ) : arcs.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No narrative arcs yet. Run a scenario with{" "}
          <code>?narrative_mode=integrated</code> to accrete story beats.
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          {arcs.map((arc) => (
            <section key={arc.agent}>
              <div className="mb-3 flex items-baseline justify-between">
                <h2 className="font-mono text-lg text-gold-400">{arc.agent}</h2>
                <span className="text-xs text-ink-300">
                  {arc.arc_length} beats · cumulative reputation{" "}
                  <RepDelta v={arc.cumulative_reputation_delta} />
                </span>
              </div>
              <ol className="relative flex flex-col gap-3 border-l border-ink-500 pl-5">
                {arc.beats.map((b, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full bg-gold-600" />
                    <div className="rounded-lg border border-ink-500 bg-ink-800 p-3">
                      <p className="text-sm text-ink-50">{b.beat}</p>
                      <div className="mt-2 flex items-center gap-3 text-[11px] text-ink-400">
                        <span className="font-mono">{b.scenario_id}</span>
                        <span className="rounded bg-ink-600 px-2 py-0.5">{b.arc_state}</span>
                        <RepDelta v={b.reputation_delta} />
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
