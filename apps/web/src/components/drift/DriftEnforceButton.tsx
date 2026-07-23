"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { runDriftScan, type DriftFinding } from "@/lib/api/client";

export function DriftEnforceButton({ wouldSuspend }: { wouldSuspend: DriftFinding[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const affected = Array.from(new Set(wouldSuspend.filter((f) => f.status === "drift").map((f) => f.cert_id)));

  async function onConfirm() {
    setBusy(true);
    setError(null);
    try {
      const report = await runDriftScan();
      setMsg(`Scanned ${report.scanned} · suspended ${report.suspended}`);
      setOpen(false);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400"
      >
        Run enforcing scan
      </button>
      {msg && <span className="text-xs text-success">{msg}</span>}
      {error && <span className="max-w-[16rem] text-xs text-danger">{error}</span>}

      <ConfirmModal
        open={open}
        title="Enforce drift suspension"
        requireWord="ENFORCE"
        confirmLabel="Suspend certs"
        busy={busy}
        onConfirm={onConfirm}
        onCancel={() => setOpen(false)}
      >
        <p>
          This will suspend <strong>{affected.length}</strong> certification
          {affected.length === 1 ? "" : "s"} whose pinned Forge version has drifted. This action is
          logged and cannot be undone from the UI.
        </p>
        {affected.length > 0 ? (
          <ul className="mt-3 max-h-40 overflow-y-auto rounded border border-ink-600 bg-ink-900/50 p-2 text-xs">
            {wouldSuspend
              .filter((f) => f.status === "drift")
              .map((f) => (
                <li key={f.cert_id} className="font-mono text-ink-200">
                  {f.agent_village_id} · {f.forge_cap} ({f.pinned_version} → {f.current_version ?? "?"})
                </li>
              ))}
          </ul>
        ) : (
          <p className="mt-3 text-xs text-warning">
            Nothing to suspend — the enforcing scan currently has 0 drifted active certs. (There are
            0 active certs at all; see the table below.)
          </p>
        )}
      </ConfirmModal>
    </span>
  );
}
