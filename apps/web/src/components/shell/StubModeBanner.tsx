"use client";

import { useEffect, useState } from "react";

import { health, type LlmMode } from "@/lib/api/client";

const DISMISS_KEY = "simforge.stub_banner_dismissed_v1";

export function StubModeBanner() {
  const [mode, setMode] = useState<LlmMode | null>(null);
  const [dismissed, setDismissed] = useState(true); // assume dismissed until we know otherwise

  useEffect(() => {
    setDismissed(sessionStorage.getItem(DISMISS_KEY) === "1");
    health
      .llmMode()
      .then(setMode)
      .catch(() => setMode(null));
  }, []);

  if (dismissed || !mode || !mode.stub_scores) return null;

  return (
    <div className="flex items-center gap-3 border-b border-warning/40 bg-warning/10 px-6 py-2 text-sm text-ink-50">
      <span className="text-warning">⚠</span>
      <span>
        Some scores are stub-generated — real LLM signal not yet enabled. Rubric dims{" "}
        <strong>P7, C1, C2</strong> are heuristic-only.
      </span>
      <a
        href="https://github.com/navigreen311/simforge/blob/main/docs/adr/ADR-0023-real-ollama-judge.md"
        target="_blank"
        rel="noreferrer"
        className="text-gold-400 hover:underline"
      >
        Learn more
      </a>
      <button
        onClick={() => {
          sessionStorage.setItem(DISMISS_KEY, "1");
          setDismissed(true);
        }}
        className="ml-auto rounded px-2 py-0.5 text-xs text-ink-300 hover:bg-ink-700 hover:text-ink-50"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
