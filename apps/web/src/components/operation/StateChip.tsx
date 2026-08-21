import type { OperationCertState } from "@/lib/api/client";
import { OPERATION_STATE_META } from "@/lib/operation";

// A single operation-cert state, rendered as a distinctly-coloured chip. Each of
// the 7 states has its own hue so never_certified / failed / stale never blur
// together and are never mistaken for a low score (spec Batch 6, item 5).
export function StateChip({ state }: { state: OperationCertState }) {
  const meta = OPERATION_STATE_META[state];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-semibold ${meta.chip}`}
      title={meta.blurb}
    >
      <span className={`h-2 w-2 rounded-full ${meta.dot}`} aria-hidden />
      {meta.label}
    </span>
  );
}

// A once-per-page key so the distinct states are legible. Ordered run-lifecycle:
// never-run → in-progress → passed → failed → stale → void.
const LEGEND_ORDER: OperationCertState[] = [
  "never_certified",
  "in_training",
  "certified",
  "failed",
  "stale_instructions",
  "stale_forge",
  "revoked",
];

export function StateLegend() {
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-400">
        Operation-cert states — distinct, never a low score
      </div>
      <ul className="grid gap-2 sm:grid-cols-2">
        {LEGEND_ORDER.map((s) => (
          <li key={s} className="flex items-start gap-2 text-xs text-ink-200">
            <span className="mt-0.5 shrink-0">
              <StateChip state={s} />
            </span>
            <span>{OPERATION_STATE_META[s].blurb}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
