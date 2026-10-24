/** Unusual-behaviour events for one source, as reported by the API. */
import type { BehaviourEvent } from '../types';
import { BEHAVIOUR_HELP, BEHAVIOUR_LABEL, endText, evidenceText } from '../lib/behaviour';
import { personColor, personLabel } from '../lib/people';

export function BehaviourList({ events }: { events: BehaviourEvent[] }) {
  return <ul className="behaviour-list">{events.map(event => <li key={event.event_id} data-severity={event.severity}
    data-ended={event.end_seconds !== null ? 'true' : undefined} title={BEHAVIOUR_HELP[event.event_type]}>
    <strong>{BEHAVIOUR_LABEL[event.event_type]}</strong>
    <span><span className="person-dot" style={{ background: personColor(event.track_id) }} aria-hidden="true" />
      {personLabel(event.track_id, event.identity)} · from <span className="num">{event.start_seconds.toFixed(1)} s</span>,
      alerted at <span className="num">{event.detected_at_seconds.toFixed(1)} s</span></span>
    <span>{evidenceText(event)} · {endText(event)}</span>
  </li>)}</ul>;
}
