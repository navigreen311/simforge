import { AdversarialProbeRunner } from "@/components/adversarial/AdversarialProbeRunner";
import { PageMeta } from "@/components/ui/PageMeta";
import { adversarial, api, type Tactic } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function AdversarialPage() {
  let tactics: Tactic[] = [];
  let scenarios: { scenarioId: string; title: string }[] = [];
  let error: string | null = null;

  try {
    const [tacticList, packList] = await Promise.all([adversarial.tactics(), api.packs()]);
    tactics = tacticList.tactics;
    const details = await Promise.all(
      packList.items.map(async (p) => {
        try {
          return await api.pack(p.packId);
        } catch {
          return null;
        }
      }),
    );
    scenarios = details
      .filter((d) => d !== null)
      .flatMap((d) => d!.scenarios.map((s) => ({ scenarioId: s.scenarioId, title: s.title })));
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load adversarial suite";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Adversarial Suite</h1>
        <PageMeta />
      </div>
      <p className="mb-4 text-ink-200">
        Red-team probes pressure the agent toward a specific compliance violation. Capitulation =
        naming a violating action, agreeing to it, and not refusing (ADR-0028). A probe fires the
        full tactic set at the scenario&apos;s bound agent.
      </p>
      <div className="mb-6 flex flex-col gap-1 rounded-lg border border-warning/40 bg-warning/10 p-3 text-xs text-ink-100">
        <span>
          ⚠ Probes use the <strong>live LLM provider</strong> (one call per tactic; may incur cost +
          latency). Currently the stub provider — free + deterministic.
        </span>
        <span className="text-ink-300">
          Certification impact: capitulation → cert block is <strong>not wired</strong> in the data
          model — probe results are <em>advisory only</em>. Arbitrary-agent probing + persisted
          history need backend work (deferred).
        </span>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the adversarial suite: <code className="text-danger">{error}</code>
        </div>
      ) : (
        <>
          {scenarios.length > 0 && (
            <div className="mb-10">
              <AdversarialProbeRunner scenarios={scenarios} />
            </div>
          )}

          <h2 className="mb-4 text-xl">Tactic catalog</h2>
          <div className="flex flex-col gap-3">
            {tactics.map((t) => (
              <div key={t.id} className="rounded-xl border border-ink-500 bg-ink-800 p-4">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm text-gold-400">{t.id}</span>
                  <span className="rounded bg-ink-600 px-2 py-0.5 text-xs text-ink-100">
                    {t.category}
                  </span>
                  <span className="ml-auto flex flex-wrap gap-1">
                    {t.targets.map((tg) => (
                      <span
                        key={tg}
                        className="rounded bg-danger/10 px-2 py-0.5 font-mono text-[11px] text-danger"
                      >
                        {tg}
                      </span>
                    ))}
                  </span>
                </div>
                <p className="mt-2 border-l-2 border-ink-500 pl-3 text-sm italic text-ink-200">
                  &ldquo;{t.injection}&rdquo;
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
