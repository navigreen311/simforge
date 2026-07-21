import { SeverityPill } from "@/components/gaps/SeverityPill";
import { gaps, type VillageOSGap } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function VillageOSGapsPage() {
  let items: VillageOSGap[] = [];
  let error: string | null = null;
  try {
    items = (await gaps.villageOs()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load gaps";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Village-OS Gaps</h1>
      <p className="mb-8 text-ink-200">
        Cognitive-framework anomalies surfaced by runs. No gaps = healthy agents.
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load gaps: <code className="text-danger">{error}</code>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-success/30 bg-success/5 p-6 text-ink-100">
          No Village-OS anomalies detected. All exercised agents are within healthy thresholds.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Ticket</th>
                <th className="px-4 py-3 font-medium">Framework</th>
                <th className="px-4 py-3 font-medium">Sev</th>
                <th className="px-4 py-3 font-medium">Summary</th>
                <th className="px-4 py-3 font-medium">Seen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {items.map((g) => (
                <tr key={g.ticketId} className="hover:bg-ink-800/60">
                  <td className="px-4 py-3 font-mono text-xs text-gold-400">{g.ticketId}</td>
                  <td className="px-4 py-3 font-mono text-xs uppercase text-ink-100">
                    {g.framework}
                  </td>
                  <td className="px-4 py-3">
                    <SeverityPill severity={g.severity} />
                  </td>
                  <td className="px-4 py-3 text-ink-50">{g.summary}</td>
                  <td className="px-4 py-3 text-ink-100">×{g.occurrenceCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
