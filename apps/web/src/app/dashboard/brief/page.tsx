import { PageMeta } from "@/components/ui/PageMeta";
import { stakeholder, type StakeholderBrief } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const TONE_BAR: Record<string, string> = {
  green: "border-success/40 bg-success/10 text-success",
  amber: "border-warning/40 bg-warning/10 text-warning",
  red: "border-danger/40 bg-danger/10 text-danger",
};

export default async function BriefPage() {
  let brief: StakeholderBrief | null = null;
  let error: string | null = null;
  try {
    brief = await stakeholder.brief();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load brief";
  }

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Stakeholder Brief</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-3xl text-ink-200">
        A plain-language executive summary of the certification program, generated from live counts —
        no fabricated confidence. Share it as-is or use it as the basis for a stakeholder update
        (v1.2).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the brief: <code className="text-danger">{error}</code>
        </div>
      ) : brief ? (
        <>
          <div className={`mb-6 rounded-xl border p-5 ${TONE_BAR[brief.tone] ?? "border-ink-500 bg-ink-800 text-ink-100"}`}>
            <div className="text-xl font-semibold">{brief.headline}</div>
            <p className="mt-2 text-sm text-ink-100">{brief.narrative}</p>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Active certs" value={brief.metrics.active_certs} />
            <Stat
              label="Open gaps"
              value={brief.metrics.open_gaps_total}
              tone={brief.metrics.open_gaps.P0 > 0 ? "bad" : brief.metrics.open_gaps_total ? "warn" : "ok"}
            />
            <Stat
              label="Ventures ready"
              value={`${brief.metrics.ventures_ready}/${brief.metrics.ventures_total}`}
            />
            <Stat
              label="Unsafe forges"
              value={brief.metrics.unsafe_forges.length}
              tone={brief.metrics.unsafe_forges.length ? "bad" : "ok"}
            />
          </div>

          <div className="mb-6 rounded-xl border border-ink-500 bg-ink-800 p-4">
            <div className="mb-2 text-sm text-ink-100">Open gaps by severity</div>
            <div className="flex gap-4 text-sm">
              {(["P0", "P1", "P2"] as const).map((sev) => (
                <span key={sev} className="font-mono">
                  <span className="text-ink-400">{sev}</span>{" "}
                  <span
                    className={
                      sev === "P0" && brief!.metrics.open_gaps[sev] > 0
                        ? "text-danger"
                        : "text-ink-100"
                    }
                  >
                    {brief.metrics.open_gaps[sev] ?? 0}
                  </span>
                </span>
              ))}
            </div>
          </div>

          <section>
            <h2 className="mb-2 text-lg">Recommended actions</h2>
            <ul className="flex flex-col gap-2">
              {brief.recommended_actions.map((a, i) => (
                <li
                  key={i}
                  className="rounded-lg border border-ink-600 bg-ink-800 px-4 py-2 text-sm text-ink-100"
                >
                  {a}
                </li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "ok" | "warn" | "bad";
}) {
  const color = tone === "bad" ? "text-danger" : tone === "warn" ? "text-warning" : "text-ink-50";
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 px-4 py-3">
      <div className={`font-display text-2xl ${color}`}>{value}</div>
      <div className="text-xs text-ink-400">{label}</div>
    </div>
  );
}
