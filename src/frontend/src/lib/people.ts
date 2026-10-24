import type { TrackId } from '../types';

/** Results stored before tracking have no IDs; they describe one person. */
export const personKey = (trackId: TrackId): number => trackId ?? 0;

export const personName = (trackId: TrackId): string => (trackId ? `Person ${trackId}` : 'Person');

// Mid-tone hues that read on both the dark video stage and light/dark surfaces.
const PALETTE = ['#2aa5b3', '#d18b1f', '#8b6ee6', '#3ea85f', '#4f86e8', '#9aa83a'];

export function personColor(trackId: TrackId): string {
  return PALETTE[(Math.max(personKey(trackId), 1) - 1) % PALETTE.length];
}

/** Group records by person, keeping the given order inside each group. */
export function byPerson<T extends { track_id?: TrackId }>(records: T[]): Map<number, T[]> {
  const groups = new Map<number, T[]>();
  for (const record of records) {
    const key = personKey(record.track_id);
    const group = groups.get(key);
    if (group) group.push(record); else groups.set(key, [record]);
  }
  return new Map([...groups].sort(([a], [b]) => a - b));
}
