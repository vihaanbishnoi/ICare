import { useCallback, useEffect, useState } from 'react';
import { fetchDangerZone, fetchRooms } from '../api/client';
import type { DangerZone, RoomSummary } from '../types';

/** One room's danger zone, refreshed while mounted. `refresh` reloads right away (after an edit). */
export function useDangerZone(room: string, intervalMs = 10_000) {
  const [state, setState] = useState<{ room: string; zone: DangerZone | null; error: string | null }>(
    { room, zone: null, error: null });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const abort = new AbortController();
    const load = async () => {
      try {
        const zone = await fetchDangerZone(room, abort.signal);
        if (!abort.signal.aborted) setState({ room, zone, error: null });
      } catch (e) {
        if (!abort.signal.aborted) setState({ room, zone: null, error: e instanceof Error ? e.message : 'The danger zone could not be loaded.' });
      }
    };
    void load();
    const timer = window.setInterval(load, intervalMs);
    return () => { abort.abort(); window.clearInterval(timer); };
  }, [room, intervalMs, tick]);

  const refresh = useCallback(() => setTick(value => value + 1), []);
  // Never show another room's data while this room loads.
  return { ...(state.room === room ? state : { zone: null, error: null }), refresh };
}

/** Rooms that already have data (falls or a photo). */
export function useRoomSummaries(intervalMs = 15_000): RoomSummary[] {
  const [rooms, setRooms] = useState<RoomSummary[]>([]);
  useEffect(() => {
    const abort = new AbortController();
    const load = async () => {
      try {
        const next = await fetchRooms(abort.signal);
        if (!abort.signal.aborted) setRooms(next);
      } catch { /* the API is offline: the page shows its own message */ }
    };
    void load();
    const timer = window.setInterval(load, intervalMs);
    return () => { abort.abort(); window.clearInterval(timer); };
  }, [intervalMs]);
  return rooms;
}
