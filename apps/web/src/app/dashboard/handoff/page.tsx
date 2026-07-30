import { PageMeta } from "@/components/ui/PageMeta";
import { handoff, type HandoffTest } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function HandoffPage() {
  let tests: HandoffTest[] = [];
  let error: string | null = null;
  try {
    tests = (await handoff.list()).handoff_tests;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load handoff tests";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Handoff Integrity</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        Department work crosses agents — outreach hands a lead to underwriting, underwriting hands a
        decision to servicing. A handoff has integrity when nothing the receiver needs is dropped,
        the chain doesn&apos;t skip a link, and consent travels with the work. Define a chain, then
        evaluate it via <code>POST /api/handoff/{"{id}"}/evaluate</code> (v1.1).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load handoff tests: <code className="text-danger">{error}</code>
        </div>
      ) : tests.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          No handoff tests defined yet. Create one via <code>POST /api/handoff</code> with an ordered
          chain of steps (from, to, provides, required, consent).
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {tests.map((t) => (
            <div key={t.id} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="text-lg text-ink-50">{t.name}</span>
                {t.scenario_id && (
                  <span className="font-mono text-xs text-ink-500">{t.scenario_id}</span>
                )}
                <span className="text-xs text-ink-400">{t.chain.length} step(s)</span>
              </div>
              <ol className="flex flex-col gap-2">
                {t.chain.map((s, i) => {
                  const missing = s.required.filter((r) => !s.provides.includes(r));
                  return (
                    <li
                      key={i}
                      className="rounded-lg border border-ink-600 bg-ink-900/40 px-3 py-2 text-sm"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-ink-100">{s.from}</span>
                        <span className="text-gold-400">→</span>
                        <span className="font-mono text-ink-100">{s.to}</span>
                        {s.consent ? (
                          <span className="rounded bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">
                            consent
                          </span>
                        ) : (
                          <span className="rounded bg-danger/15 px-2 py-0.5 text-[10px] font-semibold text-danger">
                            no consent
                          </span>
                        )}
                        {missing.length > 0 && (
                          <span className="rounded bg-danger/15 px-2 py-0.5 text-[10px] font-semibold text-danger">
                            drops {missing.join(", ")}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 text-[11px] text-ink-400">
                        provides: {s.provides.join(", ") || "—"} · requires:{" "}
                        {s.required.join(", ") || "—"}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
