import type {
  AuditEvent,
  Change,
  ChangeFilters,
  ChangeInput,
  DashboardSummary,
  Evidence,
  Health,
  Job,
  Page,
  Project
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId?: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiOptions = RequestInit & { token?: string; timeoutMs?: number };

let apiBase = "";

export function setApiBase(value: string): void {
  apiBase = value.trim().replace(/\/$/, "");
}

function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs ?? 12_000);
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("X-Request-ID", crypto.randomUUID());
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.token) headers.set("Authorization", `Bearer ${options.token}`);

  try {
    const response = await fetch(`${apiBase}${path}`, { ...options, headers, signal: controller.signal });
    const requestId = response.headers.get("X-Request-ID") ?? undefined;
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(payload.detail ?? `Request failed with ${response.status}`, response.status, requestId);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Check API availability and try again.", 408);
    }
    throw new ApiError(error instanceof Error ? error.message : "Network request failed", 0);
  } finally {
    window.clearTimeout(timeout);
  }
}

async function pageRequest<T>(path: string, token: string): Promise<Page<T>> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 12_000);
  try {
    const response = await fetch(`${apiBase}${path}`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "X-Request-ID": crypto.randomUUID()
      },
      signal: controller.signal
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { detail?: string };
      throw new ApiError(
        payload.detail ?? `Request failed with ${response.status}`,
        response.status,
        response.headers.get("X-Request-ID") ?? undefined
      );
    }
    return {
      items: (await response.json()) as T[],
      nextCursor: response.headers.get("X-Next-Cursor") ?? undefined
    };
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Check API availability and try again.", 408);
    }
    throw new ApiError(error instanceof Error ? error.message : "Network request failed", 0);
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  health: () => request<Health>("/health/ready"),
  summary: (token: string) => request<DashboardSummary>("/api/v1/dashboard/summary", { token }),
  projects: (token: string, search = "", cursor?: string) =>
    pageRequest<Project>(`/api/v1/projects${queryString({ search, cursor, limit: 50 })}`, token),
  project: (token: string, id: string) => request<Project>(`/api/v1/projects/${id}`, { token }),
  createProject: (token: string, input: Pick<Project, "name" | "source_uri" | "default_branch">) =>
    request<Project>("/api/v1/projects", { token, method: "POST", body: JSON.stringify(input) }),
  changes: (token: string, filters: ChangeFilters = {}, cursor?: string) =>
    pageRequest<Change>(
      `/api/v1/changes${queryString({
        project_id: filters.projectId,
        status: filters.status,
        kind: filters.kind,
        search: filters.search,
        cursor,
        limit: 50
      })}`,
      token
    ),
  change: (token: string, id: string) => request<Change>(`/api/v1/changes/${id}`, { token }),
  createChange: (token: string, input: ChangeInput) =>
    request<Change>("/api/v1/changes", {
      token,
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(input)
    }),
  approveChange: (token: string, change: Change, actor: string) =>
    request<Change>(`/api/v1/changes/${change.id}/approve`, {
      token,
      method: "POST",
      body: JSON.stringify({ actor, expected_version: change.version })
    }),
  cancelChange: (token: string, change: Change, actor: string, reason: string) =>
    request<Change>(`/api/v1/changes/${change.id}/cancel`, {
      token,
      method: "POST",
      body: JSON.stringify({ actor, reason, expected_version: change.version })
    }),
  jobs: (token: string, status?: string, changeId?: string, cursor?: string) =>
    pageRequest<Job>(
      `/api/v1/jobs${queryString({ status, change_id: changeId, cursor, limit: 50 })}`,
      token
    ),
  evidence: (token: string, changeId: string) =>
    request<Evidence[]>(`/api/v1/changes/${changeId}/evidence`, { token }),
  evidenceContent: (token: string, evidenceId: string) =>
    request<Record<string, unknown>>(`/api/v1/evidence/${evidenceId}/content`, { token }),
  audit: (adminToken: string, changeId?: string, cursor?: string) =>
    pageRequest<AuditEvent>(
      `/api/v1/audit-events${queryString({ change_id: changeId, cursor, limit: 50 })}`,
      adminToken
    )
};
