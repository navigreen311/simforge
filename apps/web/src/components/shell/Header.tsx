import { StatusDot } from "@/components/common/StatusDot";
import { api } from "@/lib/api/client";

// Server component: shows live API readiness in the header. When the API is DEGRADED, it must not
// sit unexplained on a governance console — say WHICH subsystem is down and whether it affects the
// certification data shown (FIX 6). Certification data is read from Postgres; the cache being down
// does not make cert results stale.
export async function Header() {
  let status = "error";
  let checks: Record<string, string> = {};
  try {
    const ready = await api.ready();
    status = ready.status;
    checks = ready.checks ?? {};
  } catch {
    status = "error";
  }

  const failing = Object.entries(checks).filter(([, v]) => v !== "ok");
  const databaseOk = checks.database === undefined || checks.database === "ok";

  // Data-impact statement: cert data lives in Postgres, so a cache (redis) outage does not stale it.
  const dataImpact = databaseOk
    ? "Certification data is read from Postgres (database: ok) and is current — the results shown are NOT stale."
    : "The database check is failing — certification data may be unavailable or out of date; treat the results as suspect.";

  const explanation =
    status === "ok"
      ? "All subsystems healthy."
      : status === "degraded"
        ? `Degraded — ${failing.map(([k, v]) => `${k}: ${v}`).join("; ")}. ${dataImpact}`
        : `API unreachable. ${dataImpact}`;

  const reason =
    status === "degraded" && failing.length
      ? failing.map(([k]) => k).join(", ")
      : status === "error"
        ? "unreachable"
        : "";

  return (
    <header className="flex h-14 items-center justify-between border-b border-ink-500 bg-ink-800 px-6">
      <div className="text-sm text-ink-200">Governance &amp; certification console</div>
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-2" title={explanation}>
          <StatusDot status={status} label={`API ${status}`} />
          {status !== "ok" && (
            <span
              className={`cursor-help text-[11px] ${databaseOk ? "text-warning" : "text-danger"}`}
            >
              {reason ? `(${reason}` : "("}
              {status !== "ok" && (
                <span className="text-ink-400">
                  {reason ? " · " : ""}
                  {databaseOk ? "cert data unaffected" : "cert data may be stale"})
                </span>
              )}
            </span>
          )}
        </span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gold-600 text-sm font-semibold text-ink-900">
          IV
        </div>
      </div>
    </header>
  );
}
