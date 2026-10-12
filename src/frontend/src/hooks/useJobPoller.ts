/** Polling and result retrieval share one cancellable lifecycle per job. */
import { useCallback, useEffect, useState } from 'react';
import { deleteJob, fetchResults, pollJob } from '../api/client';
import type { Job, Result } from '../types';

type Snapshot = { key: string; job: Job | null; result: Result | null; error: string | null; retryable: boolean };
const empty = (key: string): Snapshot => ({ key, job: null, result: null, error: null, retryable: false });

export function useJobPoller(jobId: string | null) {
  const [attempt, setAttempt] = useState(0);
  const key = `${jobId ?? ''}:${attempt}`;
  const [snapshot, setSnapshot] = useState<Snapshot>(() => empty(''));
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let disposed = false;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    async function tick() {
      let stage: 'status' | 'results' = 'status';
      try {
        const job = await pollJob(jobId!, controller.signal);
        if (disposed) return;
        failures = 0;
        if (job.state === 'failed' || job.state === 'cancelled') {
          setSnapshot({ ...empty(key), job, error: job.error?.message ?? `Analysis ${job.state}.` });
          return;
        }
        setSnapshot({ ...empty(key), job });
        if (job.state === 'completed') {
          stage = 'results';
          const result = await fetchResults(job.job_id, controller.signal);
          if (!disposed) setSnapshot({ ...empty(key), job, result });
          return;
        }
        timer = setTimeout(tick, 1000);
      } catch (error: unknown) {
        if (disposed) return;
        const status = (error as { status?: number })?.status;
        const permanent = !!status && status >= 400 && status < 500 && status !== 429;
        failures += 1;
        if (stage === 'results' || permanent || failures >= 3) {
          const message = error instanceof Error ? error.message : 'Unable to retrieve analysis.';
          setSnapshot(previous => ({
            ...(previous.key === key ? previous : empty(key)),
            error: `${stage === 'results' ? 'Result retrieval' : 'Status check'} failed: ${message}`,
            retryable: !permanent,
          }));
          return;
        }
        timer = setTimeout(tick, 3000);
      }
    }
    void tick();
    return () => { disposed = true; controller.abort(); clearTimeout(timer); };
  }, [jobId, key]);

  const retry = useCallback(() => setAttempt(value => value + 1), []);
  const cancel = useCallback(async () => {
    if (!jobId) return;
    setCancelling(true);
    try { await deleteJob(jobId); retry(); }
    catch (error) {
      setSnapshot(previous => ({ ...previous, key, error: error instanceof Error ? error.message : 'Cancellation failed.', retryable: true }));
    } finally { setCancelling(false); }
  }, [jobId, key, retry]);
  return { ...(snapshot.key === key ? snapshot : empty(key)), retry, cancel, cancelling };
}
