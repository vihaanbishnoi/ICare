/** Wording for unusual-behaviour events (rules in src/icare/inference/behaviour.py). */
import type { BehaviourEvent, BehaviourState, BehaviourType } from '../types';

export const BEHAVIOUR_LABEL: Record<BehaviourType, string> = {
  pacing: 'Repeated pacing',
  prolonged_inactivity: 'No movement',
  long_lie: 'Not up after fall',
};

export const BEHAVIOUR_HELP: Record<BehaviourType, string> = {
  pacing: 'Walked back and forth along the same line several times. Can indicate restlessness or agitation.',
  prolonged_inactivity: 'Clearly visible, with no body movement for the configured time.',
  long_lie: 'A fall was recorded and the person is still lying down: not seen sitting or standing up since.',
};

/** Merge changed events into a list by id, newest detection first. */
export function mergeEvents(previous: BehaviourEvent[], changed: BehaviourEvent[]): BehaviourEvent[] {
  if (!changed.length) return previous;
  const byId = new Map(previous.map(event => [event.event_id, event]));
  for (const event of changed) byId.set(event.event_id, event);
  return [...byId.values()].sort((a, b) => b.detected_at_seconds - a.detected_at_seconds);
}

const seconds = (value: number) => value < 60 ? `${Math.round(value)} s` : `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;

/** What was measured, in words, e.g. "5 turns" or "still 2 min 3 s". */
export function evidenceText(event: BehaviourEvent): string {
  const e = event.evidence;
  if (event.event_type === 'pacing') return `${e.turns ?? 0} turns over ${seconds(e.duration_seconds ?? 0)}`;
  if (event.event_type === 'prolonged_inactivity') return `Still for ${seconds(e.still_seconds ?? 0)}`;
  return `Down ${seconds(e.seconds_since_fall ?? 0)} after the fall`;
}

export function endText(event: BehaviourEvent): string {
  if (event.end_seconds === null) return 'Ongoing';
  return event.end_reason === 'resolved' ? `Ended at ${event.end_seconds.toFixed(1)} s`
    : event.end_reason === 'person_lost' ? 'Person left view' : 'Recording ended';
}

/** Short per-person status for the people list; null when nothing is building up. */
export function progressText(state: BehaviourState | null | undefined): string | null {
  if (!state) return null;
  if (state.active_events.length) return state.active_events.map(kind => BEHAVIOUR_LABEL[kind]).join(', ');
  if (state.evidence === 'insufficient') return 'Not clearly visible';
  if (state.down_after_fall_seconds !== null) return `Down ${seconds(state.down_after_fall_seconds)}`;
  if (state.still_seconds >= 10) return `Still ${seconds(state.still_seconds)}`;
  if (state.pacing_turns >= 2) return `${state.pacing_turns} pacing turns`;
  return null;
}
