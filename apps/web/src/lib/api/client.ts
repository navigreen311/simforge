// Typed API client for the FastAPI backend.
// Phase 1: hand-written types mirroring the API schemas. Phase 3 swaps in an
// OpenAPI-generated client (blueprint §D.5) once the surface stabilizes.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface AgentSummary {
  id: string;
  villageAgentId: string;
  name: string;
  role: string;
  departmentId: string;
  currentAutonomyLevel: string;
  gardnerFlag: boolean;
  level10Enabled: boolean;
}

export interface AgentList {
  items: AgentSummary[];
  total: number;
  page: number;
  page_size: number;
}

export interface DepartmentSummary {
  id: string;
  villageKey: string;
  name: string;
  totalAgents: number;
}

export interface DepartmentList {
  items: DepartmentSummary[];
  total: number;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, string>;
}

export interface ScenarioSummary {
  id: string;
  scenarioId: string;
  title: string;
  tier: string;
  testedAgentVillageId: string;
  sloSeconds: number;
  isGolden: boolean;
}

export interface PackSummary {
  id: string;
  packId: string;
  name: string;
  version: string;
  ownerVenture: string;
  phiRequired: boolean;
  executionModeDefault: string;
  signedBy: string | null;
  signedAt: string | null;
}

export interface PackDetail extends PackSummary {
  complianceFlags: string[];
  rubricProfile: string;
  scenarios: ScenarioSummary[];
}

export interface PackList {
  items: PackSummary[];
  total: number;
}

export interface RunSummary {
  run_id: string;
  scenario_id: string;
  agent_village_id: string;
  pack_id: string;
  status: string;
  outcome: string | null;
  execution_mode: string;
  blind_mode: boolean;
  started_at: string;
  ended_at: string | null;
  latency_ms: number | null;
  tokens_used: number | null;
  cost_usd: number | null;
}

export interface RunList {
  items: RunSummary[];
  total: number;
}

export interface TranscriptTurn {
  role: string;
  content: string;
}

export interface TraceEvent {
  timestamp: string;
  event_type: string;
  phase: string;
  turn_number: number | null;
  payload: Record<string, unknown>;
}

export interface Scorecard {
  run_id: string;
  p1_correctness: number | null;
  p2_compliance: boolean | null;
  p3_process_fidelity: number | null;
  p4_time_to_resolution: number | null;
  p5_escalation: number | null;
  p6_doc_quality: number | null;
  p7_customer_experience: number | null;
  p8_cost_discipline: number | null;
  c1_breath_coherence: number | null;
  c2_soul_stability: number | null;
  c3_fot_pressure_management: number | null;
  c4_arc_narrative_coherence: string | null;
  c5_echo_regret_load: number | null;
  c6_hfm_drive_balance: number | null;
  c7_ame_reputation_trajectory: number | null;
  cognitive_aggregate: number | null;
  readiness_gate_passed: boolean;
  auto_fail_reason: string | null;
  turn_annotations: Array<{ turn: number; tag: string; detail: string }>;
  remediation_recs: Array<{ rec: string; priority: string }> | null;
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // Dashboards are always fresh in dev; revalidation strategy tuned per-page later.
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  ready: () => apiGet<ReadyResponse>("/api/health/ready"),
  agents: (params?: { page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    const qs = q.toString();
    return apiGet<AgentList>(`/api/agents/${qs ? `?${qs}` : ""}`);
  },
  departments: () => apiGet<DepartmentList>("/api/departments/"),
  packs: () => apiGet<PackList>("/api/packs/"),
  pack: (packId: string) => apiGet<PackDetail>(`/api/packs/${packId}`),
  runs: () => apiGet<RunList>("/api/runs/"),
  run: (runId: string) => apiGet<RunSummary>(`/api/runs/${runId}`),
  transcript: (runId: string) =>
    apiGet<{ run_id: string; turns: TranscriptTurn[] }>(`/api/runs/${runId}/transcript`),
  trace: (runId: string) =>
    apiGet<{ run_id: string; events: TraceEvent[] }>(`/api/runs/${runId}/trace`),
  scorecard: (runId: string) => apiGet<Scorecard>(`/api/runs/${runId}/scorecard`),
};

/** Client-side mutation: execute a scenario run. Returns the completed run summary. */
export async function runScenario(scenarioId: string): Promise<RunSummary> {
  const res = await fetch(`${API_BASE}/api/scenarios/${scenarioId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Run failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as RunSummary;
}
