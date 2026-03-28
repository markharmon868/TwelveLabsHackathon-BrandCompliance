import type { Job, GuidelinesSample } from "./types";

const BASE = "";  // proxied via Vite to http://localhost:8000

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
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
