/**
 * API client — all calls use relative /api/v1 URLs (same-origin requirement).
 * Never construct absolute URLs here; the cookie is SameSite=strict.
 */
import type { Example, Job, Result } from '../types';

const BASE = '/api/v1';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'same-origin',
    ...init,
  });
  if (!res.ok) {
    let errBody: { error?: { code?: string; message?: string } } = {};
    try { errBody = await res.json(); } catch { /* ignore */ }
    const msg = errBody?.error?.message ?? `HTTP ${res.status}`;
    throw Object.assign(new Error(msg), { status: res.status, code: errBody?.error?.code });
  }
  return res.json() as Promise<T>;
}

/** GET /api/v1/examples */
export async function fetchExamples(): Promise<Example[]> {
  const data = await apiFetch<{ examples: Example[] }>('/examples');
  return data.examples;
}

/** POST /api/v1/jobs/example  →  202 Job */
export async function startExampleJob(exampleId: string): Promise<Job> {
  return apiFetch<Job>('/jobs/example', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ example_id: exampleId }),
  });
}

/** POST /api/v1/jobs/upload  →  202 Job */
export async function startUploadJob(file: File): Promise<Job> {
  const form = new FormData();
  form.append('file', file);
  return apiFetch<Job>('/jobs/upload', {
    method: 'POST',
    body: form,
    // Do NOT set Content-Type — browser must set multipart boundary
  });
}

/** GET /api/v1/jobs/{job_id} */
export async function pollJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/jobs/${jobId}`);
}

/** GET /api/v1/jobs/{job_id}/results  —  409 if not complete */
export async function fetchResults(jobId: string): Promise<Result> {
  return apiFetch<Result>(`/jobs/${jobId}/results`);
}

/** DELETE /api/v1/jobs/{job_id} */
export async function deleteJob(jobId: string): Promise<void> {
  await fetch(`${BASE}/jobs/${jobId}`, {
    method: 'DELETE',
    credentials: 'same-origin',
  });
}

/** GET /api/v1/ready */
export async function checkReady(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/ready`, { credentials: 'same-origin' });
    return res.ok;
  } catch {
    return false;
  }
}
