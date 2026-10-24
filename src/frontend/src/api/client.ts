/**
 * API client — all calls use relative /api/v1 URLs (same-origin requirement).
 * Never construct absolute URLs here; the cookie is SameSite=strict.
 */
import type {
  Clip, ClipList, Job, Result, LiveSession, LiveFrame, LiveHistory,
  DailyLogsResponse, DailySummaryResponse, CaretakersListResponse,
  SchedulerStatusResponse, Trigger10pmResponse, ChatMessage, ChatResponse
} from '../types';

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
  return res.status === 204 ? undefined as T : res.json() as Promise<T>;
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
export async function pollJob(jobId: string, signal?: AbortSignal): Promise<Job> {
  return apiFetch<Job>(`/jobs/${jobId}`, { signal });
}

/** GET /api/v1/jobs/{job_id}/results  —  409 if not complete */
export async function fetchResults(jobId: string, signal?: AbortSignal): Promise<Result> {
  return apiFetch<Result>(`/jobs/${jobId}/results`, { signal });
}

/** DELETE /api/v1/jobs/{job_id} */
export async function deleteJob(jobId: string): Promise<void> {
  await apiFetch<void>(`/jobs/${jobId}`, { method: 'DELETE' });
}

export function startLiveSession(): Promise<LiveSession> {
  return apiFetch('/live/sessions', { method: 'POST' });
}

export function sendLiveFrame(sessionId: string, frame: Blob, timestamp: number, signal: AbortSignal): Promise<LiveFrame> {
  return apiFetch(`/live/sessions/${encodeURIComponent(sessionId)}/frames?timestamp_seconds=${timestamp}`, {
    method: 'POST', body: frame, headers: { 'Content-Type': 'image/jpeg' }, signal,
  });
}

export function stopLiveSession(sessionId: string): Promise<{ state: string }> {
  return apiFetch(`/live/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE', keepalive: true });
}

export async function fetchLiveHistory(): Promise<LiveHistory[]> {
  const result = await apiFetch<{ sessions: LiveHistory[] }>('/live/history');
  return result.sessions;
}

/** GET /api/v1/clips: this browser's fall clips, newest first, with the storage cap in force. */
export function fetchClips(signal?: AbortSignal): Promise<ClipList> {
  return apiFetch<ClipList>('/clips', { signal });
}

/** GET /api/v1/clips/{clip_id}: 404 once the clip expired or was deleted. */
export function fetchClip(clipId: string, signal?: AbortSignal): Promise<Clip> {
  return apiFetch<Clip>(`/clips/${encodeURIComponent(clipId)}`, { signal });
}

export async function deleteClip(clipId: string): Promise<void> {
  await apiFetch<void>(`/clips/${encodeURIComponent(clipId)}`, { method: 'DELETE' });
}

/** GET /api/v1/reports/daily-logs */
export function fetchDailyLogs(signal?: AbortSignal): Promise<DailyLogsResponse> {
  return apiFetch<DailyLogsResponse>('/reports/daily-logs', { signal });
}

/** POST /api/v1/reports/summarize */
export function fetchDailySummary(model = 'llama3.2:1b', signal?: AbortSignal): Promise<DailySummaryResponse> {
  return apiFetch<DailySummaryResponse>(`/reports/summarize?model=${encodeURIComponent(model)}`, {
    method: 'POST',
    signal,
  });
}

/** GET /api/v1/reports/schedule-status */
export function fetchScheduleStatus(signal?: AbortSignal): Promise<SchedulerStatusResponse> {
  return apiFetch<SchedulerStatusResponse>('/reports/schedule-status', { signal });
}

/** POST /api/v1/reports/trigger-10pm-dispatch */
export function trigger10pmDispatch(model = 'llama3.2:1b', signal?: AbortSignal): Promise<Trigger10pmResponse> {
  return apiFetch<Trigger10pmResponse>(`/reports/trigger-10pm-dispatch?model=${encodeURIComponent(model)}`, {
    method: 'POST',
    signal,
  });
}

/** GET /api/v1/reports/caretaker-emails */
export function fetchCaretakerEmails(limit = 50, signal?: AbortSignal): Promise<CaretakersListResponse> {
  return apiFetch<CaretakersListResponse>(`/reports/caretaker-emails?limit=${encodeURIComponent(limit)}`, { signal });
}

/** POST /api/v1/chat */
export function sendChatMessage(
  message: string,
  history: ChatMessage[] = [],
  model = 'llama3.2:1b',
  signal?: AbortSignal,
): Promise<ChatResponse> {
  return apiFetch<ChatResponse>('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history, model }),
    signal,
  });
}


