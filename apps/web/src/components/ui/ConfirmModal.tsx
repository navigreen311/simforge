"use client";

import { type ReactNode, useState } from "react";

// A destructive-action confirmation that requires typing a keyword (e.g. "ENFORCE") to arm.
export function ConfirmModal({
  open,
  title,
  requireWord,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  requireWord?: string;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  if (!open) return null;
  const armed = !requireWord || typed.trim().toUpperCase() === requireWord.toUpperCase();

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onCancel}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-danger/40 bg-ink-800 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-3 text-lg font-semibold text-danger">{title}</h2>
        <div className="text-sm text-ink-100">{children}</div>
        {requireWord && (
          <label className="mt-4 block text-xs text-ink-300">
            Type <span className="font-mono text-gold-400">{requireWord}</span> to confirm:
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              className="mt-1 w-full rounded border border-ink-500 bg-ink-900 px-3 py-2 font-mono text-sm text-ink-50"
              autoFocus
            />
          </label>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded border border-ink-500 px-3 py-1.5 text-sm text-ink-200 hover:bg-ink-700"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!armed || busy}
            className="rounded bg-danger/80 px-3 py-1.5 text-sm font-semibold text-ink-50 transition-colors hover:bg-danger disabled:opacity-40"
          >
            {busy ? "Working…" : (confirmLabel ?? "Confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
