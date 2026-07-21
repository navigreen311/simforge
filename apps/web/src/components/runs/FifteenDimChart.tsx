// 15-dimension scorecard — 8 performance + 7 cognitive, as labeled bars, plus the gate.
import type { Scorecard } from "@/lib/api/client";

const PERF: Array<[keyof Scorecard, string]> = [
  ["p1_correctness", "P1 Correctness"],
  ["p3_process_fidelity", "P3 Process fidelity"],
  ["p4_time_to_resolution", "P4 Time-to-resolution"],
  ["p5_escalation", "P5 Escalation"],
  ["p6_doc_quality", "P6 Doc quality"],
  ["p7_customer_experience", "P7 Customer experience"],
  ["p8_cost_discipline", "P8 Cost discipline"],
];

const COG: Array<[keyof Scorecard, string]> = [
  ["c1_breath_coherence", "C1 Breath coherence"],
  ["c2_soul_stability", "C2 Soul stability"],
  ["c3_fot_pressure_management", "C3 FOT pressure mgmt"],
  ["c5_echo_regret_load", "C5 Echo (regret)"],
  ["c6_hfm_drive_balance", "C6 HFM balance"],
  ["c7_ame_reputation_trajectory", "C7 AME trajectory"],
];

function barColor(v: number): string {
  if (v >= 0.8) return "bg-success";
  if (v >= 0.6) return "bg-gold-500";
  return "bg-danger";
}

function Bar({ label, value }: { label: string; value: number | null }) {
  const v = value ?? 0;
  return (
    <div className="flex items-center gap-3">
      <div className="w-40 shrink-0 text-xs text-ink-200">{label}</div>
      <div className="h-2 flex-1 overflow-hidden rounded bg-ink-600">
        <div className={`h-full ${barColor(v)}`} style={{ width: `${Math.round(v * 100)}%` }} />
      </div>
      <div className="w-10 shrink-0 text-right font-mono text-xs text-ink-100">
        {value == null ? "—" : v.toFixed(2)}
      </div>
    </div>
  );
}

export function FifteenDimChart({ card }: { card: Scorecard }) {
  const passed = card.readiness_gate_passed;
  return (
    <div className="rounded-xl border border-ink-500 bg-ink-800 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg">Scorecard</h2>
        <span
          className={`rounded px-3 py-1 text-sm font-semibold ${
            passed ? "bg-success/15 text-success" : "bg-danger/15 text-danger"
          }`}
        >
          {passed ? "GATE PASSED" : "GATE FAILED"}
          {card.auto_fail_reason ? ` · ${card.auto_fail_reason}` : ""}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-ink-300">
            <span>Performance</span>
            <span>
              P2 Compliance:{" "}
              <span className={card.p2_compliance ? "text-success" : "text-danger"}>
                {card.p2_compliance ? "pass" : "FAIL"}
              </span>
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {PERF.map(([k, label]) => (
              <Bar key={k} label={label} value={card[k] as number | null} />
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-ink-300">
            <span>Cognitive</span>
            <span>
              C4 ARC: <span className="text-ink-100">{card.c4_arc_narrative_coherence ?? "—"}</span>
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {COG.map(([k, label]) => (
              <Bar key={k} label={label} value={card[k] as number | null} />
            ))}
          </div>
          <div className="mt-3 flex items-center gap-3 border-t border-ink-600 pt-3">
            <div className="w-40 shrink-0 text-xs font-semibold text-gold-400">
              Cognitive aggregate
            </div>
            <div className="flex-1 text-right font-mono text-sm text-gold-400">
              {card.cognitive_aggregate?.toFixed(3) ?? "—"}
            </div>
          </div>
        </div>
      </div>

      {card.remediation_recs && card.remediation_recs.length > 0 && (
        <div className="mt-5 border-t border-ink-600 pt-4">
          <div className="mb-2 text-xs text-ink-300">Remediation</div>
          <ul className="list-inside list-disc text-sm text-ink-100">
            {card.remediation_recs.map((r, i) => (
              <li key={i}>
                {r.rec} <span className="text-xs text-ink-400">({r.priority})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
