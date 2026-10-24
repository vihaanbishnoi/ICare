import { useEffect, useState } from 'react';
import { fetchResidents } from '../api/client';
import type { ResidentList } from '../types';

/** Enrolled residents. `unavailable` when the API cannot be reached; `refresh` reloads after a change. */
export function useResidents(): { list: ResidentList | null; unavailable: boolean; refresh: () => void } {
  const [list, setList] = useState<ResidentList | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const abort = new AbortController();
    const load = async () => {
      try {
        const next = await fetchResidents(abort.signal);
        if (!abort.signal.aborted) { setList(next); setUnavailable(false); }
      } catch {
        if (!abort.signal.aborted) setUnavailable(true);
      }
    };
    void load();
    return () => abort.abort();
  }, [version]);

  return { list, unavailable, refresh: () => setVersion(v => v + 1) };
}
