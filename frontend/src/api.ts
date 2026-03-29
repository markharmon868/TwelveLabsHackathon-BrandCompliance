import type { Job, GuidelinesSample, GuidelinesData } from "./types";

const BASE = "";  // proxied via Vite in dev; served by FastAPI in prod

export const STORAGE_KEY = "tl_api_key";

export function getStoredApiKey(): string {
  return localStorage.getItem(STORAGE_KEY) ?? "";
}

export function saveApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key.trim());
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}

function authHeaders(): Record<string, string> {
  const key = getStoredApiKey();
  return key ? { "X-TwelveLabs-Key": key } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  Object.entries(authHeaders()).forEach(([k, v]) => headers.set(k, v));
  const res = await fetch(BASE + path, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function validateApiKey(key: string): Promise<{ valid: boolean; error?: string }> {
  const res = await fetch("/health/key", {
    headers: { "X-TwelveLabs-Key": key },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    return { valid: false, error: body.detail ?? "Invalid key" };
  }
  return res.json();
}

export async function submitJob(
  videoFile: File,
  options:
    | { type: "sample"; filename: string }
    | { type: "file"; file: File }
    | { type: "json"; json: string }
): Promise<Job> {
  const form = new FormData();
  form.append("video_file", videoFile);

  if (options.type === "sample") {
    form.append("sample_guidelines", options.filename);
  } else if (options.type === "file") {
    form.append("guidelines_file", options.file);
  } else {
    form.append("guidelines_json", options.json);
  }

  return request<Job>("/jobs", { method: "POST", body: form });
}

export async function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`);
}

export async function listJobs(): Promise<Job[]> {
  const data = await request<{ jobs: Job[]; total: number }>("/jobs");
  return data.jobs;
}

export async function listSamples(): Promise<GuidelinesSample[]> {
  return request<GuidelinesSample[]>("/guidelines/samples");
}

export async function getGuideline(filename: string): Promise<GuidelinesData> {
  return request<GuidelinesData>(`/guidelines/samples/${filename}`);
}

export async function createGuideline(data: GuidelinesData): Promise<{ filename: string }> {
  return request<{ filename: string }>("/guidelines/samples", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function updateGuideline(filename: string, data: GuidelinesData): Promise<{ filename: string }> {
  return request<{ filename: string }>(`/guidelines/samples/${filename}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function reviewJob(
  jobId: string,
  decision: "approved" | "rejected" | "escalated",
  notes?: string
): Promise<Job> {
  return request<Job>(`/jobs/${jobId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, notes: notes || null }),
  });
}

export async function deleteGuideline(filename: string): Promise<void> {
  const res = await fetch(`/guidelines/samples/${filename}`, { method: "DELETE" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Delete failed: ${res.status}`);
  }
}

// ---------------------------------------------------------------------------
// Frame.io integration
// ---------------------------------------------------------------------------

export interface FrameioStatus {
  connected: boolean;
  user: { name: string; email: string; account_id: string } | null;
  error?: string;
}

export interface FrameioConfig {
  default_guidelines: string;
  workspace_id: string;
  webhook_id: string;
  webhook_url: string;
  custom_action_id: string;
  custom_action_url: string;
}

export interface FrameioWorkspace {
  id: string;
  name: string;
}

export async function getFrameioStatus(): Promise<FrameioStatus> {
  return request<FrameioStatus>("/frameio/status");
}

export async function getFrameioConfig(): Promise<FrameioConfig> {
  return request<FrameioConfig>("/frameio/config");
}

export async function updateFrameioConfig(data: Partial<FrameioConfig>): Promise<FrameioConfig> {
  return request<FrameioConfig>("/frameio/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function getFrameioWorkspaces(): Promise<FrameioWorkspace[]> {
  const data = await request<{ workspaces: FrameioWorkspace[] }>("/frameio/workspaces");
  return data.workspaces;
}

export async function registerFrameioWebhook(
  workspaceId: string,
  webhookUrl: string
): Promise<{ webhook_id: string; status: string }> {
  return request("/frameio/webhook/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId, webhook_url: webhookUrl }),
  });
}

export async function registerFrameioCustomAction(
  actionUrl: string
): Promise<{ custom_action_id: string; status: string }> {
  return request("/frameio/custom-action/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action_url: actionUrl }),
  });
}

export async function triggerFrameioAudit(
  assetId: string,
  guidelinesFilename: string
): Promise<{ job_id: string; asset_id: string }> {
  return request("/frameio/audit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_id: assetId, guidelines_filename: guidelinesFilename }),
  });
}
