"use client";

import { useState } from "react";

export function CopyButton({ value, label = "copy" }: { value: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        } catch {
          /* clipboard may be blocked; no-op */
        }
      }}
      className="rounded border border-ink-500 px-1.5 py-0.5 text-[10px] text-ink-300 hover:bg-ink-700 hover:text-ink-50"
    >
      {done ? "✓ copied" : label}
    </button>
  );
}
