import { PageMeta } from "@/components/ui/PageMeta";
import { coldStart, type ColdStartPlaybook } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const SLA_TONE: Record<string, string> = {
  met: "bg-success/15 text-success",
  within: "bg-success/15 text-success",
  at_risk: "bg-warning/15 text-warning",
  breached: "bg-danger/15 text-danger",
  unknown: "bg-ink-600 text-ink-200",
};

export default async function ColdStartPage() {
  let playbooks: ColdStartPlaybook[] = [];
  let error: string | null = null;
  try {
    playbooks = (await coldStart.all()).playbooks;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load playbooks";
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Cold-Start Playbook</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        The path a new venture walks from workflow sign-off to a certifiable v1 Pack, tracked against
        an SLA. Every milestone is derived from live state — the pack either has scenarios or it
        doesn&apos;t, is signed or isn&apos;t — so the board can&apos;t drift from reality (v1.2).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load playbooks: <code className="text-danger">{error}</code>
        </div>
      ) : playbooks.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-4 text-sm text-ink-300">
          No ventures registered yet.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {playbooks.map((p) => (
            <div key={p.venture} className="rounded-xl border border-ink-500 bg-ink-800 p-5">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="text-lg text-ink-50">{p.name}</span>
                <span className="font-mono text-xs text-ink-500">{p.venture}</span>
                {p.ready ? (
                  <span className="rounded bg-success/15 px-2 py-0.5 text-xs font-semibold text-success">
                    v1 pack ready
                  </span>
                ) : (
                  <span className="rounded bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">
                    {p.progress} · blocked on {p.blocking_step}
                  </span>
                )}
                <span
                  className={`ml-auto rounded px-2 py-0.5 text-xs font-semibold ${SLA_TONE[p.sla_status] ?? "bg-ink-600 text-ink-200"}`}
                  title={`${p.elapsed_days ?? "?"} of ${p.sla_target_days} SLA days elapsed`}
                >
                  SLA: {p.sla_status}
                </span>
              </div>
              <ol className="flex flex-wrap gap-2">
                {p.milestones.map((m, i) => (
                  <li
                    key={m.key}
                    className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs ${
                      m.done
                        ? "border-success/30 bg-success/10 text-success"
                        : "border-ink-600 bg-ink-900/40 text-ink-400"
                    }`}
                  >
                    <span className="font-mono">{i + 1}</span>
                    <span>{m.label}</span>
                    <span>{m.done ? "✓" : "○"}</span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
