"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { runDriftScan } from "@/lib/api/client";

export function DriftScanButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function onClick() {
    if (!confirm("Run an enforcing drift scan? Drifted certs will be auto-suspended.")) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const report = await runDriftScan();
      setResult(`Scanned ${report.scanned} · suspended ${report.suspended}`);
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
        onClick={onClick}
        disabled={busy}
        className="rounded bg-gold-500 px-4 py-2 text-sm font-semibold text-ink-900 transition-colors hover:bg-gold-400 disabled:opacity-50"
      >
        {busy ? "Scanning…" : "Run enforcing scan"}
      </button>
      {result && <span className="text-xs text-success">{result}</span>}
      {error && <span className="max-w-[16rem] text-xs text-danger">{error}</span>}
    </span>
  );
}
