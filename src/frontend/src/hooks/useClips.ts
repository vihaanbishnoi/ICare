import { useEffect, useState } from 'react';
import { fetchClip, fetchClips } from '../api/client';
import type { Clip, ClipList } from '../types';

const PENDING_POLL_MS = 1000;
const PENDING_POLL_LIMIT = 60;

/** One clip by id. A live clip is pending until the second after the fall has been captured. */
export function useClip(clipId: string): { clip: Clip | null; error: string | null } {
  const [state, setState] = useState<{ id: string; clip: Clip | null; error: string | null }>(
    { id: clipId, clip: null, error: null });

  useEffect(() => {
    const abort = new AbortController();
    let timer = 0;
    let polls = 0;
    const load = async () => {
      try {
        const clip = await fetchClip(clipId, abort.signal);
        if (abort.signal.aborted) return;
        setState({ id: clipId, clip, error: null });
        if (clip.status === 'pending' && ++polls < PENDING_POLL_LIMIT) timer = window.setTimeout(load, PENDING_POLL_MS);
      } catch (e) {
        if (abort.signal.aborted) return;
        const status = (e as { status?: number }).status;
        setState({ id: clipId, clip: null, error: status === 404
          ? 'This clip has expired or was removed. Fall clips are kept for 24 hours.'
          : e instanceof Error ? e.message : 'The clip could not be loaded.' });
      }
    };
    void load();
    return () => { abort.abort(); window.clearTimeout(timer); };
  }, [clipId]);

  // Never show the previous clip's data while a different id is loading.
  return state.id === clipId ? { clip: state.clip, error: state.error } : { clip: null, error: null };
}

/** All of this browser's clips, refreshed while mounted. `unavailable` when the API cannot be reached. */
export function useClipList(intervalMs = 5000): { list: ClipList | null; unavailable: boolean } {
  const [list, setList] = useState<ClipList | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const abort = new AbortController();
    const load = async () => {
      try {
        const next = await fetchClips(abort.signal);
        if (!abort.signal.aborted) { setList(next); setUnavailable(false); }
      } catch {
        if (!abort.signal.aborted) setUnavailable(true);
      }
    };
    void load();
    const timer = window.setInterval(load, intervalMs);
    return () => { abort.abort(); window.clearInterval(timer); };
  }, [intervalMs]);

  return { list, unavailable };
}
