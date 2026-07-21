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
};
