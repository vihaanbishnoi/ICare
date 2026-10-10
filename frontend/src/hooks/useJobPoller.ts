/**
 * Custom hook: polls a job until terminal state, returns the latest Job.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { pollJob } from '../api/client';
import type { Job } from '../types';

const TERMINAL: string[] = ['completed', 'failed', 'cancelled'];
const POLL_MS = 1000;

export function useJobPoller(jobId: string | null) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!jobId) { setJob(null); setError(null); return; }

    let cancelled = false;

    async function tick() {
      if (cancelled) return;
      try {
        const j = await pollJob(jobId!);
        if (cancelled) return;
        setJob(j);
        setError(null);
        if (!TERMINAL.includes(j.state)) {
          timerRef.current = setTimeout(tick, POLL_MS);
        }
      } catch (e: unknown) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Polling error');
        timerRef.current = setTimeout(tick, POLL_MS * 3);
      }
    }

    tick();
    return () => {
      cancelled = true;
      stop();
    };
  }, [jobId, stop]);

  return { job, error, stopPolling: stop };
}
