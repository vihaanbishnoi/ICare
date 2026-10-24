import { useEffect, useState } from 'react';
import { fetchBehaviourEvents } from '../api/client';
import type { BehaviourEvent } from '../types';

/** This browser's behaviour events, refreshed while mounted. `unavailable` when the API cannot be reached. */
export function useBehaviourEvents(intervalMs = 4000): { events: BehaviourEvent[] | null; unavailable: boolean } {
  const [events, setEvents] = useState<BehaviourEvent[] | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    const load = async () => {
      try {
        const next = await fetchBehaviourEvents(abort.signal);
        if (!abort.signal.aborted) { setEvents(next); setUnavailable(false); }
      } catch {
        if (!abort.signal.aborted) setUnavailable(true);
      }
    };
    void load();
    const timer = window.setInterval(load, intervalMs);
    return () => { abort.abort(); window.clearInterval(timer); };
  }, [intervalMs]);

  return { events, unavailable };
}
