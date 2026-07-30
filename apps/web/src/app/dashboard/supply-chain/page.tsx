import { PageMeta } from "@/components/ui/PageMeta";
import { supplyChain, type Sbom } from "@/lib/api/client";

export const dynamic = "force-dynamic";

const FLAG_TONE: Record<string, string> = {
  denylisted: "bg-danger/15 text-danger",
  unpinned: "bg-warning/15 text-warning",
};

export default async function SupplyChainPage() {
  let sbom: Sbom | null = null;
  let error: string | null = null;
  try {
    sbom = await supplyChain.sbom();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load SBOM";
  }

  const flagged = sbom?.components.filter((c) => c.flags.length > 0) ?? [];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-1 flex items-start justify-between">
        <h1 className="text-3xl">Supply Chain</h1>
        <PageMeta />
      </div>
      <p className="mb-6 max-w-4xl text-ink-200">
        A Software Bill of Materials generated from SimForge&apos;s own manifests, with governance
        flags for pin discipline and a denylist. A live vulnerability feed is an external seam — until
        one is wired, this reports what&apos;s verifiable from the manifests rather than inventing CVE
        data (v1.2).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load the SBOM: <code className="text-danger">{error}</code>
        </div>
      ) : sbom ? (
        <>
          <div className="mb-6 flex flex-wrap gap-3">
            <Stat label="Components" value={sbom.counts.total} />
            <Stat label="Runtime" value={sbom.counts.runtime} />
            <Stat label="Flagged" value={sbom.counts.flagged} tone={sbom.counts.flagged ? "warn" : "ok"} />
            <Stat label="Unpinned" value={sbom.counts.unpinned} tone={sbom.counts.unpinned ? "warn" : "ok"} />
            <Stat label="Denylisted" value={sbom.counts.denylisted} tone={sbom.counts.denylisted ? "bad" : "ok"} />
          </div>

          <div className="mb-6 rounded-xl border border-ink-500 bg-ink-800 p-4 text-xs text-ink-300">
            Vulnerability feed:{" "}
            {sbom.vuln_feed_configured ? (
              <span className="text-success">configured</span>
            ) : (
              <span className="text-ink-400">not configured (set VULN_FEED_URL to enable)</span>
            )}
          </div>

          {flagged.length > 0 && (
            <section className="mb-8">
              <h2 className="mb-3 text-lg">Governance flags</h2>
              <div className="overflow-x-auto rounded-xl border border-ink-500">
                <table className="min-w-full text-left text-sm">
                  <thead className="bg-ink-800 text-ink-200">
                    <tr>
                      <th className="px-4 py-2 font-medium">Component</th>
                      <th className="px-4 py-2 font-medium">Version</th>
                      <th className="px-4 py-2 font-medium">Ecosystem</th>
                      <th className="px-4 py-2 font-medium">Flags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ink-600">
                    {flagged.map((c) => (
                      <tr key={`${c.ecosystem}-${c.name}`}>
                        <td className="px-4 py-2 font-mono text-xs text-ink-100">{c.name}</td>
                        <td className="px-4 py-2 font-mono text-xs text-ink-300">{c.version}</td>
                        <td className="px-4 py-2 text-ink-300">{c.ecosystem}</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-1">
                            {c.flags.map((f) => (
                              <span
                                key={f}
                                className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                  FLAG_TONE[f] ?? "bg-ink-600 text-ink-100"
                                }`}
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-3 text-lg">Full inventory</h2>
            <div className="overflow-x-auto rounded-xl border border-ink-500">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-800 text-ink-200">
                  <tr>
                    <th className="px-4 py-2 font-medium">Component</th>
                    <th className="px-4 py-2 font-medium">Version</th>
                    <th className="px-4 py-2 font-medium">Ecosystem</th>
                    <th className="px-4 py-2 font-medium">Scope</th>
                    <th className="px-4 py-2 font-medium">Pinned</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-600">
                  {sbom.components.map((c) => (
                    <tr key={`${c.ecosystem}-${c.name}-${c.scope}`}>
                      <td className="px-4 py-2 font-mono text-xs text-ink-100">{c.name}</td>
                      <td className="px-4 py-2 font-mono text-xs text-ink-300">{c.version}</td>
                      <td className="px-4 py-2 text-ink-300">{c.ecosystem}</td>
                      <td className="px-4 py-2 text-ink-400">{c.scope}</td>
                      <td className="px-4 py-2">
                        {c.pinned ? (
                          <span className="text-success">yes</span>
                        ) : (
                          <span className="text-warning">no</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "ok" | "warn" | "bad" }) {
  const color =
    tone === "bad" ? "text-danger" : tone === "warn" ? "text-warning" : "text-ink-50";
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 px-4 py-3">
      <div className={`font-display text-2xl ${color}`}>{value}</div>
      <div className="text-xs text-ink-400">{label}</div>
    </div>
  );
}
