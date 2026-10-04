export type Health = {
  status: "ok" | "degraded";
  database: "ok" | "error";
  version: string;
};

export type Project = {
  id: string;
  name: string;
  source_uri: string;
  default_branch: string;
  inventory: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type Change = {
  id: string;
  project_id: string;
  kind: "dependency" | "model";
  status: string;
  title: string;
  spec: Record<string, unknown>;
  risk_score: number;
  risk_reasons: string[];
  requested_by: string;
  approved_by: string | null;
  approved_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

export type Job = {
  id: string;
  change_id: string;
  status: string;
  attempts: number;
  max_attempts: number;
  lease_owner: string | null;
  lease_expires_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  id: string;
  change_id: string;
  kind: string;
  storage_uri: string;
  sha256: string;
  summary: Record<string, unknown>;
  created_at: string;
};

export type AuditEvent = {
  id: string;
  change_id: string | null;
  actor: string;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
};

export type DashboardSummary = {
  project_count: number;
  change_count: number;
  active_change_count: number;
  evidence_count: number;
  queue_depth: number;
  dead_letter_count: number;
  unpublished_event_count: number;
  success_rate: number;
  changes_by_status: Record<string, number>;
  changes_by_kind: Record<string, number>;
  jobs_by_status: Record<string, number>;
  generated_at: string;
};

export type Page<T> = { items: T[]; nextCursor?: string };

export type ChangeFilters = {
  projectId?: string;
  status?: string;
  kind?: string;
  search?: string;
};

export type ChangeInput = {
  project_id: string;
  title: string;
  requested_by: string;
  spec: Record<string, unknown>;
};
