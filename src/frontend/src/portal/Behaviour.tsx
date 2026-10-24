/** Unusual-behaviour alerts from the real detector (live camera and uploaded videos) in the manager console. */
import type { BehaviourEvent } from '../types';
import { BEHAVIOUR_HELP, BEHAVIOUR_LABEL, endText, evidenceText } from '../lib/behaviour';
import { personLabel } from '../lib/people';
import { ago, clock } from './data';
import { Icon } from './ui';

const source = (e: BehaviourEvent) => e.source_kind === 'live' ? 'Live camera' : 'Uploaded video';

export function BehaviourToasts({ events, onOpen, onDismiss }: {
  events: BehaviourEvent[]; onOpen: () => void; onDismiss: (id: string) => void;
}) {
  if (!events.length) return null;
  return <div className="p-toasts" role="status">{events.map(e => <div key={e.event_id} className="p-toast" data-tone={e.severity}>
    <span className="p-toast__pulse"><Icon name="alert" size={18} /></span>
    <div className="p-toast__body">
      <strong>{BEHAVIOUR_LABEL[e.event_type]} · Room DET</strong>
      <span>{personLabel(e.track_id, e.identity)} · {source(e)} · {evidenceText(e)}</span>
      <div className="p-toast__actions">
        <button type="button" className="p-btn p-btn--lime p-btn--sm" onClick={() => { onDismiss(e.event_id); onOpen(); }}>View</button>
        <button type="button" className="p-btn p-btn--glass p-btn--sm" onClick={() => onDismiss(e.event_id)}>Dismiss</button>
      </div>
    </div>
  </div>)}</div>;
}

export function BehaviourView({ today, checked, onCheck, now, unavailable }: {
  today: BehaviourEvent[]; checked: Set<string>; onCheck: (id: string) => void; now: number; unavailable: boolean;
}) {
  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Behaviour alerts</h2>
        <p className="p-muted">{today.length} today · {today.filter(e => !checked.has(e.event_id)).length} not yet checked</p>
        <p className="p-muted p-small">{unavailable ? 'The detector API is not running, so behaviour alerts cannot be loaded.'
          : 'From the real detector: the live camera and uploaded videos (Room DET).'}</p></div>
    </div>
    <section className="p-card p-card--flush">
      <table className="p-table">
        <thead><tr><th>Behaviour</th><th>Person</th><th>Source</th><th>Time</th><th>What was measured</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{today.map(e => <tr key={e.event_id} data-open={!checked.has(e.event_id) ? 'true' : undefined}>
          <td><span className="p-badge p-badge--plain" data-tone={e.severity === 'urgent' ? 'bad' : 'warn'}>{BEHAVIOUR_LABEL[e.event_type]}</span></td>
          <td>{personLabel(e.track_id, e.identity)}</td>
          <td>{source(e)}</td>
          <td className="num">{clock(Date.parse(e.created_at_utc))} <span className="p-muted">· {ago(Date.parse(e.created_at_utc), now)}</span></td>
          <td>{evidenceText(e)}</td>
          <td>{endText(e)}</td>
          <td className="p-table__act">{checked.has(e.event_id)
            ? <span className="p-badge" data-tone="good">Checked</span>
            : <button type="button" className="p-btn p-btn--primary p-btn--sm" onClick={() => onCheck(e.event_id)}><Icon name="check" size={14} />Mark checked</button>}</td>
        </tr>)}
        {!today.length && <tr><td colSpan={7} className="p-empty">No unusual behaviour detected today.</td></tr>}</tbody>
      </table>
    </section>
    <section className="p-card">
      <header className="p-card__head"><span>What is watched</span></header>
      <ul className="p-rules">
        {(['pacing', 'prolonged_inactivity', 'long_lie'] as const).map(kind => <li key={kind}>
          <b>{BEHAVIOUR_LABEL[kind]}</b><span>{BEHAVIOUR_HELP[kind]}</span></li>)}
      </ul>
      <p className="p-muted p-small">Based only on body movement from the camera. A person who is not clearly visible is never flagged. Thresholds are experimental settings and these alerts are prompts for a staff check, not diagnoses.</p>
    </section>
  </div>;
}
