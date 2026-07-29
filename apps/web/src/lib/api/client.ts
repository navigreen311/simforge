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
  locale: string;
  signedBy: string | null;
  signedAt: string | null;
  supersedesPackId: string | null;
}

export interface PackCard extends PackSummary {
  complianceFlags: string[];
  scenarioCount: number;
  tierCounts: Record<string, number>; // { foundational, intermediate, advanced_crisis }
  goldenCount: number;
}

export interface PackDetail extends PackSummary {
  complianceFlags: string[];
  rubricProfile: string;
  scenarios: ScenarioSummary[];
}

export interface PackList {
  items: PackCard[];
  total: number;
}

export interface FlagInfo {
  label: string;
  tooltip: string;
  phi: boolean;
  jurisdiction: string | null;
}

export interface FlagCatalog {
  flags: Record<string, FlagInfo>;
  legend: Record<string, string>;
}

export interface VentureSuggestion {
  phiRequired: boolean;
  complianceFlags: string[];
  rubricProfile: string;
}

export interface AuthoringOptions {
  ventures: string[];
  rubrics: string[];
  jurisdiction_flags: string[];
  venture_suggestions: Record<string, VentureSuggestion>;
}

export interface PackScenarioInput {
  scenarioId: string;
  testedAgentVillageId: string;
  sloSeconds: number;
  testedForgeCaps: string[];
  trainingDomains: string[];
  isGolden: boolean;
  seed: number;
}

export interface PackCreateRequest {
  title: string;
  ownerVenture: string;
  version: string;
  phiRequired: boolean;
  complianceFlags: string[];
  executionModeDefault: string;
  rubricProfile: string;
  scenarios: PackScenarioInput[];
}

export interface PackCreateResponse {
  ok: boolean;
  packId: string;
  scenarios: number;
  issues: { severity: string; code: string; message: string; location: string }[];
  error: string | null;
}

// ---- Venture Registry (source of truth for the venture field) ----
export interface Venture {
  id: string;
  slug: string;
  name: string;
  description: string;
  status: string; // active | in_development | archived
  scenarioCode: string;
  defaultComplianceFlags: string[];
  internalForges: string[];
  capabilities: string[];
  createdBy: string;
  createdAt: string;
  packCount: number;
  committedScenarioCount: number;
  capabilityCount: number;
}

export interface VenturePackRef {
  packId: string;
  name: string;
  version: string;
  scenarioCount: number;
}

export interface SpecDocumentRef {
  id: string;
  filename: string;
  uploadedAt: string;
  proposalsCount: number;
  scenariosCount: number;
}

export interface VentureDetail extends Venture {
  packs: VenturePackRef[];
  specDocuments: SpecDocumentRef[];
}

export interface VentureCreateRequest {
  name: string;
  slug: string;
  description?: string;
  status?: string;
  scenarioCode?: string | null;
  defaultComplianceFlags?: string[];
  internalForges?: string[];
  capabilities?: string[];
}

export interface EnrichmentProposal {
  description: string;
  complianceFlags: string[];
  internalForges: string[];
  capabilities: string[];
  confidence: number | null;
}

export interface ProducedScenario {
  publicId: string;
  title: string;
  tier: string;
}

export interface SpecUploadResponse {
  ok: boolean;
  error: string | null;
  specDocumentId: string | null;
  filename: string | null;
  enrichment: EnrichmentProposal | null;
  produced_scenarios: ProducedScenario[];
}

export const ventures = {
  list: () => apiGet<{ items: Venture[]; total: number }>("/api/ventures/"),
  detail: (slug: string) => apiGet<VentureDetail>(`/api/ventures/${slug}`),
  create: (body: VentureCreateRequest) => apiPost<Venture>("/api/ventures/", body),
  update: (slug: string, body: Partial<VentureCreateRequest>) =>
    apiPatch<Venture>(`/api/ventures/${slug}`, body),
  uploadSpec: (slug: string, file: File) =>
    apiPostFile<SpecUploadResponse>(`/api/ventures/${slug}/specs`, file),
};

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

/** Build a `?a=1&b=2` query string from a params object, skipping null/undefined/empty. */
function qs<T extends object>(params?: T): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export interface RunQuery {
  status?: string;
  tier?: string;
  execution_mode?: string;
  blind?: boolean;
  agent?: string;
  pack?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

export interface RunCounts {
  total: number;
  by_status: Record<string, number>;
  passed: number;
  failed: number;
  errored: number;
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const api = {
  ready: () => apiGet<ReadyResponse>("/api/health/ready"),
  agents: (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    department_id?: string;
    autonomy_level?: string;
    gardner_flag?: boolean;
    level10?: boolean;
    has_active_certs?: boolean;
  }) => apiGet<AgentList>(`/api/agents/${qs(params)}`),
  agentsLegend: () => apiGet<AgentsLegend>("/api/agents/legend"),
  createAgent: (body: AgentCreateRequest) => apiPost<AgentSummary>("/api/agents/", body),
  bulkImportAgents: (rows: BulkAgentRow[]) =>
    apiPost<BulkImportResponse>("/api/agents/bulk", { rows }),
  departments: () => apiGet<DepartmentList>("/api/departments/"),
  scenarios: () => apiGet<{ items: ScenarioSummary[]; total: number }>("/api/scenarios/"),
  packs: () => apiGet<PackList>("/api/packs/"),
  pack: (packId: string) => apiGet<PackDetail>(`/api/packs/${packId}`),
  flagCatalog: () => apiGet<FlagCatalog>("/api/packs/flag-catalog"),
  authoringOptions: () => apiGet<AuthoringOptions>("/api/packs/authoring-options"),
  createPack: (body: PackCreateRequest) =>
    apiPost<PackCreateResponse>("/api/packs/create", body),
  newPackVersion: (packId: string, body: PackCreateRequest) =>
    apiPost<PackCreateResponse>(`/api/packs/${packId}/new-version`, body),
  runs: (params?: RunQuery) => apiGet<RunList>(`/api/runs/${qs(params)}`),
  runCounts: (params?: RunQuery) => apiGet<RunCounts>(`/api/runs/counts${qs(params)}`),
  run: (runId: string) => apiGet<RunSummary>(`/api/runs/${runId}`),
  transcript: (runId: string) =>
    apiGet<{ run_id: string; turns: TranscriptTurn[] }>(`/api/runs/${runId}/transcript`),
  trace: (runId: string) =>
    apiGet<{ run_id: string; events: TraceEvent[] }>(`/api/runs/${runId}/trace`),
  scorecard: (runId: string) => apiGet<Scorecard>(`/api/runs/${runId}/scorecard`),
};

/** Client-side mutation: execute a scenario run. Returns the completed run summary. */
export interface SummaryPlain {
  code: string | null;
  what: string;
  why: string;
  action: string;
}

export interface SoftwareGap {
  ticketId: string;
  forge: string;
  module: string;
  severity: string;
  summary: string;
  summary_technical: string;
  summary_plain: SummaryPlain | null;
  detail: string;
  proposedFix: string | null;
  status: string;
  occurrenceCount: number;
  linearUrl: string | null;
}

export interface VillageOSGap {
  ticketId: string;
  framework: string;
  severity: string;
  summary: string;
  detail: string;
  proposedFix: string | null;
  status: string;
  occurrenceCount: number;
}

export const gaps = {
  software: () => apiGet<{ items: SoftwareGap[]; total: number }>("/api/gaps/software"),
  villageOs: () => apiGet<{ items: VillageOSGap[]; total: number }>("/api/gaps/village-os"),
};

export interface AgentCert {
  id: string;
  agentId: string;
  forgeCap: string;
  tier: string;
  status: string;
  issuedAt: string;
  expiresAt: string;
  revokedAt: string | null;
  revocationReason: string | null;
  certSnapshotId: string;
  capabilityLabel: string;
  capabilityForge: string;
  capabilityDescription: string;
}

export interface CertQuery {
  status?: string;
  tier?: string;
  forge?: string;
  agent?: string;
  expiring_within?: number;
  search?: string;
}

export const certs = {
  agent: (params?: CertQuery) =>
    apiGet<{ items: AgentCert[]; total: number }>(`/api/certs/agent${qs(params)}`),
};

// ---- UI-support endpoints (UI P0 audit) ----
export interface LlmMode {
  agent_provider: string;
  judge_provider: string;
  agent_effective: string;
  judge_effective: string;
  stub_scores: boolean;
}

export interface SystemStatus {
  llm_provider: string;
  llm_judge_provider: string;
  llm_judge_effective: string;
  village_fingerprint: string;
  constitution_version: string | null;
  hsm_provider: string;
  hsm_status: string;
}

export interface IntegrityWarning {
  agent_id: string;
  warning_type: string;
  detail: string;
  autonomy_level: string;
  active_certs: number;
  severity: string;
}

export interface AgentCertRollup {
  agent_village_id: string;
  active_certs: number;
  total_certs: number;
  last_certified_at: string | null;
}

export interface LadderLevel {
  level: string;
  index: number;
  meaning: string;
  is_floor: boolean;
}

export interface AgentFlagInfo {
  key: string;
  label: string;
  meaning: string;
  defined: boolean;
}

export interface AgentsLegend {
  floor: string;
  levels: LadderLevel[];
  flags: AgentFlagInfo[];
}

export interface AgentCreateRequest {
  name: string;
  villageAgentId?: string | null;
  role?: string;
  departmentId: string;
  gardnerFlag?: boolean;
  level10Enabled?: boolean;
}

export interface BulkAgentRow {
  name: string;
  id?: string;
  role?: string;
  department?: string;
  flags?: string;
}

export interface BulkRowResult {
  index: number;
  name: string;
  villageAgentId: string | null;
  status: string; // imported | skipped | error
  reason: string | null;
}

export interface BulkImportResponse {
  imported: number;
  skipped: number;
  errored: number;
  results: BulkRowResult[];
}

export const health = {
  llmMode: () => apiGet<LlmMode>("/api/health/llm-mode"),
  systemStatus: () => apiGet<SystemStatus>("/api/health/system-status"),
};

export interface DashboardSummary {
  agents: number;
  runs: number;
  active_certs: number;
  issued_certs: number;
  open_software_gaps: number;
  open_village_os_gaps: number;
}

export const dashboard = {
  summary: () => apiGet<DashboardSummary>("/api/dashboard/summary"),
  integrityWarnings: () =>
    apiGet<{ warnings: IntegrityWarning[]; total: number }>("/api/dashboard/integrity-warnings"),
  runsPerDay: (days = 14) =>
    apiGet<{ days: number; series: { date: string; count: number }[] }>(
      `/api/dashboard/runs-per-day?days=${days}`,
    ),
  agentCerts: () => apiGet<{ items: AgentCertRollup[] }>("/api/dashboard/agent-certs"),
};

export interface ConstitutionCurrent {
  version: string;
  ratified_at: string;
  ratified_by: string;
  content_hash: string;
  superseded_by: string | null;
}

export interface Amendment {
  amendment_id: string;
  status: string;
  proposed_by: string;
  cooling_ends_at: string;
  impact: Record<string, unknown> | null;
}

export interface LineageSubgraph {
  nodes: string[];
  edges: Array<{ from: string; to: string; relation: string }>;
}

export interface ConstitutionVersion {
  version: string;
  ratified_at: string;
  ratified_by: string;
  content_hash: string;
  superseded_by: string | null;
  active: boolean;
}

export interface ConstitutionContent extends ConstitutionCurrent {
  yaml: string;
}

export interface AmendmentFull {
  amendment_id: string;
  status: string;
  proposed_by: string;
  proposed_at: string | null;
  cooling_ends_at: string;
  ratified_at: string | null;
  ratified_by: string | null;
  diff_yaml: string;
  impact: Record<string, unknown> | null;
}

export const governance = {
  current: () => apiGet<ConstitutionCurrent>("/api/constitution/current"),
  history: () => apiGet<{ amendments: AmendmentFull[] }>("/api/constitution/history"),
  versions: () => apiGet<{ versions: ConstitutionVersion[] }>("/api/constitution/versions"),
  version: (v: string) => apiGet<ConstitutionContent>(`/api/constitution/${v}`),
};

export const lineage = {
  subgraph: (urn: string, hops = 2) =>
    apiGet<LineageSubgraph>(`/api/lineage/subgraph/${urn}?hops=${hops}`),
};

export interface CapabilityLabel {
  cap_id: string;
  forge: string;
  label: string;
  description: string;
}

export const capabilities = {
  labels: () =>
    apiGet<{ capabilities: Record<string, CapabilityLabel> }>("/api/capabilities/"),
};

// ---- Scenario Bank (reviewable scenario library; nothing auto-commits) ----
export interface BankScenario {
  id: string;
  publicId: string;
  scenarioId: string | null;
  title: string;
  pack: string;
  family: string;
  tier: string;
  situation: string;
  status: string; // draft | in_review | committed | rejected | archived
  aiDrafted: boolean;
  sourceType: string; // legacy | manual | paste | document | web | youtube | video
  createdBy: string;
  createdAt: string;
}

export interface BankScenarioDetail extends BankScenario {
  expectedBehaviors: string[];
  adversarialTactics: string[];
  jurisdictionFlags: string[];
  sourceRef: string | null;
  sourceExcerpt: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  version: number;
  supersedesId: string | null;
  updatedAt: string;
}

export interface BankQuery {
  status?: string;
  pack?: string;
  family?: string;
  tier?: string;
  source_type?: string;
  ai_drafted?: boolean;
  search?: string;
}

// The editable candidate an extraction proposes (pre-fills the review form). Never saved as-is.
// pack/family/tier are null when the model couldn't map them to the vocab — the human then picks
// them (listed in unmapped_fields). Title/situation are always grounded in the source.
export interface ExtractedScenario {
  title: string;
  pack: string | null;
  family: string | null;
  tier: string | null;
  situation: string;
  expected_behaviors: string[];
  adversarial_tactics: string[];
  jurisdiction_flags: string[];
  confidence: number | null;
  unmapped_fields: string[];
}

export interface ExtractResponse {
  ok: boolean;
  error: string | null;
  confidence: number | null;
  scenario: ExtractedScenario | null;
  source_excerpt: string | null;
  source_ref: string | null;
}

export interface BankVocabulary {
  packs: string[];
  families: string[];
  tiers: string[];
}

// Body for saving a human-approved draft (manual authoring OR an approved extraction).
export interface DraftBody {
  title: string;
  pack: string;
  family: string;
  tier: string;
  situation: string;
  expectedBehaviors: string[];
  adversarialTactics: string[];
  jurisdictionFlags: string[];
  aiDrafted: boolean;
  sourceType: string;
  sourceRef?: string | null;
  sourceExcerpt?: string | null;
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

async function apiPostFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API ${path} failed: ${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
  content: string;
  content_chars: number;
  score: number | null;
  published_date: string | null;
}

export interface WebSearchResponse {
  available: boolean;
  provider: string;
  query: string;
  results: WebSearchResult[];
  error: string | null;
}

export interface TranscriptResponse {
  available: boolean;
  source_kind: string; // youtube | file
  text: string;
  chars: number;
  error: string | null;
  meta: Record<string, unknown>;
}

export const scenarioBank = {
  list: (params?: BankQuery) =>
    apiGet<{ items: BankScenario[]; total: number }>(`/api/scenario-bank/${qs(params)}`),
  counts: () =>
    apiGet<{ by_status: Record<string, number>; total: number; awaiting_review: number }>(
      "/api/scenario-bank/counts",
    ),
  detail: (publicId: string) =>
    apiGet<BankScenarioDetail>(`/api/scenario-bank/${publicId}`),
  vocabulary: () => apiGet<BankVocabulary>("/api/scenario-bank/vocabulary"),
  // Extraction proposes a candidate — saves NOTHING. The caller reviews before saving a draft.
  extract: (body: { source_text: string; source_type: string; source_ref?: string | null }) =>
    apiPost<ExtractResponse>("/api/scenario-bank/extract", body),
  extractDocument: (file: File) =>
    apiPostFile<ExtractResponse>("/api/scenario-bank/extract-document", file),
  // The two-stage human promotion. createDraft = stage 1 (draft). commit = stage 2 (scn.* id).
  createDraft: (body: DraftBody) =>
    apiPost<BankScenarioDetail>("/api/scenario-bank/drafts", body),
  editDraft: (publicId: string, body: Partial<DraftBody>) =>
    apiPatch<BankScenarioDetail>(`/api/scenario-bank/${publicId}`, body),
  commit: (publicId: string) =>
    apiPost<BankScenarioDetail>(`/api/scenario-bank/${publicId}/commit`, {}),
  reject: (publicId: string) =>
    apiPost<BankScenarioDetail>(`/api/scenario-bank/${publicId}/reject`, {}),
  // Web-search ingestion — finds real sources; each result feeds the same extract→review→commit path.
  webSearchStatus: () =>
    apiGet<{ available: boolean; provider: string }>("/api/scenario-bank/web-search/status"),
  webSearch: (query: string) =>
    apiPost<WebSearchResponse>("/api/scenario-bank/web-search", { query }),
  // Video / YouTube ingestion — a transcript feeds the same extract→review→commit path.
  transcriptStatus: () =>
    apiGet<{ youtube_available: boolean; file_available: boolean }>(
      "/api/scenario-bank/transcript/status",
    ),
  youtubeTranscript: (url: string) =>
    apiPost<TranscriptResponse>("/api/scenario-bank/transcript/youtube", { url }),
  transcribeFile: (file: File) =>
    apiPostFile<TranscriptResponse>("/api/scenario-bank/transcript/file", file),
};

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

// ---- Time-travel run replay (ADR-0032) ----
export interface ReplayDimDiff {
  dim: string;
  original: number | string | boolean | null;
  replay: number | string | boolean | null;
}

export interface ReplayComparison {
  original_run_id: string;
  replay_run_id: string;
  scenario_id: string;
  deterministic: boolean;
  transcript_identical: boolean;
  original_outcome: string | null;
  replay_outcome: string | null;
  original_gate_passed: boolean | null;
  replay_gate_passed: boolean | null;
  scorecard_diffs: ReplayDimDiff[];
}

export const replayRun = (runId: string) =>
  apiPost<ReplayComparison>(`/api/runs/${runId}/replay`);

// ---- Incident Command + budget (ADR-0039/0040) ----
export interface BlastRadius {
  agents: string[];
  forge_caps: string[];
  departments: string[];
}

export interface CapLabel {
  cap_id: string;
  forge: string;
  label: string;
  description: string;
}

export interface Incident {
  kind: string;
  severity: string; // critical | high | medium
  summary: string;
  count: number;
  blast_radius: BlastRadius;
  demo_driven: boolean;
  agent_names: Record<string, string>; // villageAgentId → display name
  cap_labels: Record<string, CapLabel>; // cap id → friendly label (reused catalog)
}

export interface BudgetMode {
  spent_usd: number;
  cap_usd: number;
  remaining_usd: number;
  exceeded: boolean;
}

export interface IncidentReport {
  safe_mode: { active: boolean; reason: string | null; activated_by: string | null; domains: string[] };
  budget: { month: string; modes: Record<string, BudgetMode> };
  incidents: Incident[];
  counts: Record<string, number>;
  total_incidents: number;
  status: string; // ok | degraded | critical
}

export const incident = {
  status: () => apiGet<IncidentReport>("/api/incident/status"),
};

// ---- Village narrative mode (ADR-0035) ----
export interface NarrativeBeat {
  agent: string;
  scenario_id: string;
  outcome: string | null;
  arc_state: string;
  reputation_delta: number;
  beat: string;
}

export interface NarrativeArc {
  agent: string;
  beats: NarrativeBeat[];
  cumulative_reputation_delta: number;
  arc_length: number;
}

export const narrative = {
  arc: (agentVillageId: string) =>
    apiGet<NarrativeArc>(`/api/narrative/agent/${agentVillageId}/arc`),
};

export const runNarrativeScenario = (scenarioId: string) =>
  apiPost<RunSummary>(`/api/scenarios/${scenarioId}/run?narrative_mode=integrated`);

// ---- Live run monitor (Part E) ----
export interface LaunchLiveResponse {
  run_id: string;
  warnings: string[];
  agent_village_id: string;
  integrated: boolean;
}

export interface LiveTraceEvent {
  timestamp: string;
  event_type: string;
  phase: string;
  turn_number: number | null;
  payload: Record<string, unknown>;
}

export interface LiveRunView {
  run_id: string;
  status: string; // queued | running | scoring | passed | failed | errored
  done: boolean;
  execution_mode: string;
  integrated: boolean;
  scenario_id: string;
  scenario_title: string;
  tier: string;
  agent_village_id: string;
  agent_name: string;
  started_at: string;
  ended_at: string | null;
  elapsed_ms: number;
  current_phase: string | null;
  current_turn: number;
  outcome: string | null;
  transcript: { role: string; content: string }[];
  trace: LiveTraceEvent[];
  forges_called: string[];
  tokens_used: number | null;
  latency_ms: number | null;
  cost_usd: number | null;
  scorecard: Scorecard | null;
}

export const launchLiveRun = (scenarioId: string, integrated = false) =>
  apiPost<LaunchLiveResponse>(
    `/api/scenarios/${scenarioId}/run-live${integrated ? "?integrated=true" : ""}`,
  );

export const runLive = (runId: string) => apiGet<LiveRunView>(`/api/runs/${runId}/live`);

// ---- Cohort analytics + cognitive canary (ADR-0034) ----
export interface CohortAgentRow {
  agent: string;
  role: string;
  runs: number;
  dims: Record<string, number | null>;
  aggregate_percentile: number | null;
}

export interface CohortAnalytics {
  department: string;
  cohort_size: number;
  dimensions: string[];
  agents: CohortAgentRow[];
}

export interface SnapshotStatus {
  snapshot_dates: number;
  total_snapshots: number;
  latest_date: string | null;
  drift_available: boolean;
}

export const cohort = {
  analytics: (departmentKey: string) =>
    apiGet<CohortAnalytics>(`/api/cohort/department/${departmentKey}/analytics`),
  snapshotStatus: () => apiGet<SnapshotStatus>("/api/cohort/snapshots/status"),
};

export const captureCognitiveSnapshots = () =>
  apiPost<{ date: string; captured: number; agents: { agent: string; drift_magnitude: number }[] }>(
    "/api/cohort/snapshots",
  );

// ---- Golden Benchmark (ADR-0033) ----
export interface GoldenScenario {
  scenario_id: string;
  title: string;
  tier: string;
}

export interface GoldenDiff {
  dim: string;
  expected: number | string | boolean | null;
  actual: number | string | boolean | null;
}

export interface GoldenResult {
  scenario_id: string;
  status: string; // match | regression | no_baseline | missing
  diffs: GoldenDiff[];
}

export interface GoldenReport {
  total: number;
  matched: number;
  regressions: number;
  passed: boolean;
  results: GoldenResult[];
}

export interface GoldenBaselineEntry {
  outcome: string | null;
  gate_passed: boolean | null;
  dims: Record<string, number | string | boolean | null>;
}

export interface GoldenBaseline {
  note?: string;
  provider?: string;
  committed_by?: string;
  committed_at?: string;
  hash?: string;
  titles?: Record<string, string>;
  scenarios: Record<string, GoldenBaselineEntry>;
}

export interface GoldenRunHistoryEntry {
  id: string;
  passed: boolean;
  total: number;
  matched: number;
  regressions: number;
  ran_at: string | null;
  ran_by: string;
  results: GoldenResult[];
}

export const golden = {
  scenarios: () =>
    apiGet<{ scenarios: GoldenScenario[]; total: number }>("/api/golden/scenarios"),
  baseline: () => apiGet<GoldenBaseline>("/api/golden/baseline"),
  runHistory: (limit = 5) =>
    apiGet<{ runs: GoldenRunHistoryEntry[] }>(`/api/golden/run-history?limit=${limit}`),
};

export const runGoldenSuite = () => apiPost<GoldenReport>("/api/golden/run");

// ---- Jurisdiction Engine (ADR-0019) ----
export interface Jurisdiction {
  code: string;
  name: string;
  level: string;
  regulators: string[];
  required_flags: string[];
  phi_flags: string[];
  effective_date: string | null;
  source_citation: string | null;
}

export interface CoverageReport {
  jurisdictions: string[];
  phi_required: boolean;
  required_flags: string[];
  present_flags: string[];
  missing_flags: string[];
  extra_flags: string[];
  satisfied: boolean;
}

export const jurisdictions = {
  list: () => apiGet<{ jurisdictions: Jurisdiction[] }>("/api/jurisdictions/"),
  packCoverage: (packId: string) =>
    apiGet<{ pack_id: string } & CoverageReport>(`/api/jurisdictions/coverage/pack/${packId}`),
};

// ---- Drift Canary (ADR-0017) ----
export interface DriftFinding {
  cert_id: string;
  agent_village_id: string;
  forge: string;
  forge_cap: string;
  pinned_version: string;
  current_version: string | null;
  status: string; // "drift" | "unreachable"
}

export interface DriftReport {
  scanned: number;
  drifted_certs: number;
  suspended: number;
  dry_run: boolean;
  findings: DriftFinding[];
}

export interface ConstitutionDriftFinding {
  cert_id: string;
  agent: string;
  capability: string; // raw cap id; friendly label via cap_labels
  cert_status: string;
  pinned_constitution: string | null;
  current_constitution: string | null;
  stale: boolean;
}

export interface ConstitutionDriftReport {
  current_constitution: string | null;
  scanned: number;
  stale_certs: number;
  active_stale_certs: number;
  enforced: boolean;
  cap_labels: Record<string, CapLabel>; // cap id → friendly label (shared catalog)
  agent_names: Record<string, string>; // villageAgentId → display name
  findings: ConstitutionDriftFinding[];
}

export const drift = {
  status: () => apiGet<DriftReport>("/api/drift/status"),
  constitution: () => apiGet<ConstitutionDriftReport>("/api/drift/constitution"),
};

export const runDriftScan = () => apiPost<DriftReport>("/api/drift/scan");

// ---- PDP / runtime authorization (ADR-0024) ----
export interface AuthDecision {
  decision: string; // allow | deny | step_up_approval_required | downgrade_and_retry
  reason_code: string;
  reason_detail: string;
  ttl_seconds: number;
  required_approver: string | null;
  fail_policy: string;
}

export interface EffectivePermission {
  action: string;
  tier: string;
  cert_status: string;
  decision: string;
  reason_code: string;
  capability_label: string;
  capability_forge: string;
}

export interface EffectivePermissions {
  subject_agent_id: string;
  autonomy_level: string;
  permissions: EffectivePermission[];
}

export const pdp = {
  effective: (agentVillageId: string) =>
    apiGet<EffectivePermissions>(`/api/pdp/agent/${agentVillageId}/effective`),
};

export const pdpDecide = (body: {
  subject_agent_id: string;
  action: string;
  resource?: string | null;
  context?: Record<string, unknown>;
}) => apiPost<AuthDecision>("/api/pdp/decide", body);

// ---- Meta-Eval (ADR-0027) ----
export type MetaVerdict = "dead" | "inverted" | "weak" | "working" | "insufficient";

export interface DimStats {
  dim: string;
  n: number;
  mean: number | null;
  stddev: number | null;
  min: number | null;
  max: number | null;
  mean_passed: number | null;
  mean_failed: number | null;
  discrimination: number | null;
  flags: string[];
  verdict: MetaVerdict;
}

export interface MetaEvalReport {
  n_scorecards: number;
  n_passed: number;
  n_failed: number;
  pass_rate: number;
  dimensions: DimStats[];
  flagged_dimensions: string[];
  verdict_counts: Record<MetaVerdict, number>;
  working_dimensions: string[];
  pack_id: string | null;
}

export interface RemediationIntent {
  intent: string;
  note: string;
  updated_by: string;
}

export const metaEval = {
  report: (packId?: string) =>
    apiGet<MetaEvalReport>(`/api/meta-eval/report${packId ? `?pack_id=${packId}` : ""}`),
  intents: () => apiGet<{ intents: Record<string, RemediationIntent> }>("/api/meta-eval/intents"),
  setIntent: (dim: string, intent: string, note = "") =>
    apiPut<RemediationIntent>(`/api/meta-eval/intents/${dim}`, { intent, note }),
};

// ---- Adversarial red-team (ADR-0028) ----
export interface Tactic {
  id: string;
  category: string;
  name: string;
  description: string;
  injection: string;
  targets: string[];
}

export interface ProbeResult {
  tactic: string;
  category: string;
  resisted: boolean;
  capitulated: boolean;
  matched_marker: string | null;
  response_excerpt: string;
  name: string;
  injection: string;
}

export interface AdversarialReport {
  scenario_id: string;
  scenario_title: string;
  agent: string;
  agent_name: string;
  provider: string;
  verdict: string; // resisted | partial | capitulated | no_probes
  probes_run: number;
  resisted: number;
  capitulated: number;
  resistance_rate: number;
  results: ProbeResult[];
  failures: ProbeResult[];
}

export interface ProbeHistoryEntry {
  id: string;
  scenario_id: string;
  scenario_title: string;
  agent: string;
  provider: string;
  verdict: string;
  probes_run: number;
  resisted: number;
  capitulated: number;
  resistance_rate: number;
  ran_at: string | null;
  results: ProbeResult[];
}

export const adversarial = {
  tactics: () => apiGet<{ detection: string; tactics: Tactic[] }>("/api/adversarial/tactics"),
  history: (limit = 10) =>
    apiGet<{ probes: ProbeHistoryEntry[] }>(`/api/adversarial/history?limit=${limit}`),
};

export const probeScenario = (scenarioId: string, agentId?: string) =>
  apiPost<AdversarialReport>(
    `/api/adversarial/probe/scenario/${scenarioId}${agentId ? `?agent_id=${agentId}` : ""}`,
  );

// ---- Agent training (ADR-0026) ----
export interface TrainingProposal {
  id: string;
  agentId: string;
  runId: string | null;
  weakDims: string[];
  currentPromptVersion: string;
  proposedPromptVersion: string;
  rationale: string;
  proposedRefinement: string;
  status: string; // proposed | approved | rejected
  autoApplied: boolean;
  reviewedBy: string | null;
  reviewedAt: string | null;
  createdAt: string;
}

export interface ConsequenceCert {
  cap: string;
  label: string;
}

export interface ProposalConsequence {
  kind: "applied" | "preview" | "none";
  promoted_on?: string | null;
  certs: ConsequenceCert[];
  inferred: boolean;
}

export interface EnrichedProposal {
  id: string;
  agent_id: string;
  agent_village_id: string | null;
  agent_name: string | null;
  run_id: string | null;
  run_hash: string | null;
  scenario_id: string | null;
  scenario_title: string | null;
  weak_dims: string[];
  current_prompt_version: string;
  proposed_prompt_version: string;
  rationale: string;
  proposed_refinement: string;
  status: string; // proposed | approved | rejected
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  consequence: ProposalConsequence;
}

export const training = {
  proposals: (params?: { status?: string; agent_village_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.agent_village_id) q.set("agent_village_id", params.agent_village_id);
    const qs = q.toString();
    return apiGet<TrainingProposal[]>(`/api/training/proposals${qs ? `?${qs}` : ""}`);
  },
  enriched: () => apiGet<{ proposals: EnrichedProposal[] }>("/api/training/proposals/enriched"),
};

export const approveProposal = (id: string) =>
  apiPost<Record<string, unknown>>(`/api/training/proposals/${id}/approve`, {});
export const rejectProposal = (id: string, reason = "") =>
  apiPost<Record<string, unknown>>(`/api/training/proposals/${id}/reject`, { reason });

// ---- Integrated execution (ADR-0025) ----
export interface IntegratedAction {
  action_id: string;
  agent: string | null;
  action: string | null;
  decision?: string;
  reason_code?: string;
  applied?: boolean;
  status: string; // applied | blocked | reverted
  reverted?: boolean;
  reverted_by?: string;
}

export interface LedgerAction {
  action_id: string;
  agent: string;
  agent_name: string;
  action: string;
  capability_label: string;
  capability_forge: string | null;
  decision: string | null;
  reason_code: string | null;
  applied: boolean | null;
  status: string; // applied | blocked | reverted
  reverted: boolean;
  reverted_by: string | null;
  recorded_at: string;
  current_decision: string | null;
  current_reason_code: string | null;
  historical: boolean;
}

export interface LedgerRun {
  run_id: string;
  scenario_id: string;
  scenario_title: string | null;
  agent: string | null;
  agent_name: string | null;
  started_at: string | null;
  actions: LedgerAction[];
}

export interface IntegratedLedger {
  integrated_execution_enabled: boolean;
  runs: LedgerRun[];
}

export const execution = {
  status: () => apiGet<{ integrated_execution_enabled: boolean }>("/api/execution/status"),
  runActions: (runId: string) =>
    apiGet<{ run_id: string; actions: IntegratedAction[] }>(
      `/api/execution/run/${runId}/actions`,
    ),
  ledger: () => apiGet<IntegratedLedger>("/api/execution/ledger"),
};
