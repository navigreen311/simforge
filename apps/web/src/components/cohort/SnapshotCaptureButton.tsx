"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { captureCognitiveSnapshots } from "@/lib/api/client";

export function SnapshotCaptureButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setBusy(true);
    setError(null);
    setMsg(null);
    try {
      const r = await captureCognitiveSnapshots();
      setMsg(`Captured ${r.captured} snapshot(s) for ${r.date}`);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Capture failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={busy}
        className="rounded bg-ink-700 px-3 py-1.5 text-xs font-semibold text-ink-50 transition-colors hover:bg-ink-600 disabled:opacity-50"
        title="Capture today's cognitive snapshot for every agent (idempotent per day)"
      >
        {busy ? "Capturing…" : "Capture daily snapshots"}
      </button>
      {msg && <span className="text-[10px] text-success">{msg}</span>}
      {error && <span className="max-w-[16rem] text-[10px] text-danger">{error}</span>}
    </span>
  );
}
