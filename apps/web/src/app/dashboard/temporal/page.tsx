import { PageMeta } from "@/components/ui/PageMeta";
import { temporal, type TemporalScenario } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function TemporalPage() {
  let scenarios: TemporalScenario[] = [];
  let error: string | null = null;
  try {
    scenarios = (await temporal.list()).temporal_scenarios;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load temporal scenarios";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Temporal Realism</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        Real work isn&apos;t turn-synchronous: consequences land after a delay, signals arrive out of
        band, deadlines detonate if missed. This engine models those dynamics over{" "}
        <em>virtual turns</em> — a deterministic simulation, not a live clock — so an agent can be
        scored on how it handles time pressure. A time-bomb detonates unless the agent takes its
        defuse action on or before the deadline turn (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load temporal scenarios: <code className="text-danger">{error}</code>
        </div>
      ) : scenarios.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          No temporal scenarios defined yet. Create one via <code>POST /api/temporal</code>, then
          simulate an agent&apos;s per-turn actions against it with{" "}
          <code>POST /api/temporal/{"{id}"}/simulate</code>.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {scenarios.map((s) => (
            <div key={s.id} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="text-lg text-ink-50">{s.name}</span>
                {s.scenario_id && (
                  <span className="font-mono text-xs text-ink-500">{s.scenario_id}</span>
                )}
              </div>

              {s.events.length > 0 && (
                <div className="mb-3">
                  <div className="mb-1 text-xs uppercase tracking-wide text-ink-400">
                    Scheduled events
                  </div>
                  <ul className="flex flex-col gap-1 text-sm">
                    {s.events.map((e, i) => (
                      <li key={i} className="flex items-center gap-2 text-ink-200">
                        <span className="rounded bg-ink-700 px-2 py-0.5 font-mono text-xs">
                          turn {e.at_turn}
                        </span>
                        <span className="rounded bg-ink-700 px-2 py-0.5 text-xs text-ink-300">
                          {e.kind}
                        </span>
                        <span>{e.description}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {s.time_bombs.length > 0 && (
                <div>
                  <div className="mb-1 text-xs uppercase tracking-wide text-ink-400">Time-bombs</div>
                  <ul className="flex flex-col gap-1 text-sm">
                    {s.time_bombs.map((b, i) => (
                      <li key={i} className="flex flex-wrap items-center gap-2 text-ink-200">
                        <span className="rounded bg-danger/15 px-2 py-0.5 font-mono text-xs text-danger">
                          deadline turn {b.deadline_turn}
                        </span>
                        <span>
                          defuse with <span className="font-mono text-gold-400">{b.defuse}</span>
                        </span>
                        {b.consequence && (
                          <span className="text-ink-400">— else: {b.consequence}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
