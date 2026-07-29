// One authoritative dimension-label source, reused by Meta-Eval and Cohort Analytics so the two
// never disagree about what a dimension is called or which way it points. Plain names + a short
// badge + a one-line tip, keyed by the canonical meta-eval label. Cohort uses the longer
// scorecard-attribute keys, so those are aliased to the same entries.
//
// Direction/definitions for the cognitive dims are confirmed from the scorer source
// (services/evaluation/dimensions/*), NOT invented — every numeric cognitive dim is higher-better
// (C5 is stored as 1 − regret, so higher = less regret).

export interface DimensionInfo {
  label: string; // short badge, e.g. "C1 BREATH" / "P1"
  name: string; // plain name, e.g. "Belief coherence"
  tip: string;
}

// Keyed by the canonical meta-eval label.
const DIMENSIONS: Record<string, DimensionInfo> = {
  p1_correctness: { label: "P1", name: "Correctness", tip: "Whether the agent reached the correct outcome." },
  p2_compliance: { label: "P2", name: "Compliance (pass/fail)", tip: "A boolean gate input — did the agent stay within compliance rules. Not a numeric dimension." },
  p3_process_fidelity: { label: "P3", name: "Process fidelity", tip: "Whether the agent followed the required steps/procedure." },
  p4_time_to_resolution: { label: "P4", name: "Time to resolution", tip: "How quickly the agent resolved the task." },
  p5_escalation: { label: "P5", name: "Escalation handling", tip: "Whether the agent escalated to a human when it should have." },
  p6_doc_quality: { label: "P6", name: "Documentation quality", tip: "Quality of the notes/records the agent produced." },
  p7_cx: { label: "P7", name: "Customer experience", tip: "Quality of the interaction from the customer's side (LLM-judged)." },
  p8_cost_discipline: { label: "P8", name: "Cost discipline", tip: "Whether the agent kept resource/tool/token cost in check." },
  c1_breath: { label: "C1 BREATH", name: "Belief coherence", tip: "How consistently the agent's responses reflect its declared worldview, values, ethics, and habits. Higher is better." },
  c2_soul: { label: "C2 SOUL", name: "Emotional stability", tip: "Whether the emotional trajectory stayed appropriate — no runaway hostility, inappropriate calm, or unresolved grudges. Higher is better." },
  c3_fot: { label: "C3 FOT", name: "Pressure management", tip: "How well the agent handled time/pressure (an elevated-but-stable state still scores well). Higher is better." },
  c4_arc: { label: "C4 ARC", name: "Narrative coherence (categorical)", tip: "A categorical label (stable / sudden_shift), not a 0–1 score — so it has no numeric column." },
  c5_echo: { label: "C5 ECHO", name: "Regret management", tip: "Scored as 1 − regret load, so a HIGHER number means LESS accumulated regret. Higher is better." },
  c6_hfm: { label: "C6 HFM", name: "Motive balance", tip: "Balance across the agent's human fundamental motives. Higher is better." },
  c7_ame: { label: "C7 AME", name: "Reputation trajectory", tip: "Reputation/standing with a small rising/declining adjustment. Higher is better." },
  cognitive_aggregate: { label: "Aggregate", name: "Cognitive aggregate", tip: "Mean of the cognitive dimensions above. Higher is better." },
};

// Cohort + Golden use the full scorecard-attribute keys → alias them to the canonical entries.
const ALIASES: Record<string, string> = {
  p7_customer_experience: "p7_cx",
  c1_breath_coherence: "c1_breath",
  c2_soul_stability: "c2_soul",
  c3_fot_pressure_management: "c3_fot",
  c4_arc_narrative_coherence: "c4_arc",
  c5_echo_regret_load: "c5_echo",
  c6_hfm_drive_balance: "c6_hfm",
  c7_ame_reputation_trajectory: "c7_ame",
};

function humanize(key: string): string {
  const s = key.replace(/^[pc]\d+_/, "").replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function describeDimension(key: string): DimensionInfo {
  const canonical = DIMENSIONS[key] ?? DIMENSIONS[ALIASES[key] ?? ""];
  if (canonical) return canonical;
  return { label: key, name: humanize(key), tip: `Dimension '${key}'. No plain description on file yet.` };
}

// The three LLM-judge dims (stub-scored when the judge provider is stub). Everything else is a
// deterministic heuristic scorer — so a zero-variance heuristic dim is NOT explained by the stub.
export const JUDGE_DIMS = new Set(["p7_cx", "c1_breath", "c2_soul"]);

export function scorerFor(dim: string): "stub-judge" | "heuristic" {
  return JUDGE_DIMS.has(dim) ? "stub-judge" : "heuristic";
}
