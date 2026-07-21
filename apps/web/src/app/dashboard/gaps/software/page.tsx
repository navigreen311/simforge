import { SeverityPill } from "@/components/gaps/SeverityPill";
import { gaps, type SoftwareGap } from "@/lib/api/client";

export const dynamic = "force-dynamic";

export default async function SoftwareGapsPage() {
  let items: SoftwareGap[] = [];
  let error: string | null = null;
  try {
    items = (await gaps.software()).items;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load gaps";
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-3xl">Software Gaps</h1>
      <p className="mb-8 text-ink-200">
        Forge defects surfaced by scenario runs (routed to Linear in staging/prod).
      </p>

      {error ? (
        <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm">
          Could not load gaps: <code className="text-danger">{error}</code>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-ink-500 bg-ink-800 p-6 text-ink-200">
          No software gaps yet. Run an advanced-crisis scenario to surface Forge friction.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-ink-500">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-800 text-ink-200">
              <tr>
                <th className="px-4 py-3 font-medium">Ticket</th>
                <th className="px-4 py-3 font-medium">Forge / module</th>
                <th className="px-4 py-3 font-medium">Sev</th>
                <th className="px-4 py-3 font-medium">Summary</th>
                <th className="px-4 py-3 font-medium">Seen</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-600">
              {items.map((g) => (
                <tr key={g.ticketId} className="hover:bg-ink-800/60">
                  <td className="px-4 py-3 font-mono text-xs text-gold-400">{g.ticketId}</td>
                  <td className="px-4 py-3 text-ink-100">
                    <span className="font-mono text-xs">{g.forge}</span>
                    <span className="text-ink-400"> / {g.module}</span>
                  </td>
                  <td className="px-4 py-3">
                    <SeverityPill severity={g.severity} />
                  </td>
                  <td className="px-4 py-3 text-ink-50">{g.summary}</td>
                  <td className="px-4 py-3 text-ink-100">×{g.occurrenceCount}</td>
                  <td className="px-4 py-3 text-ink-100">{g.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
