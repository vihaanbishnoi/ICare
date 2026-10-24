/** Danger zones: where falls happen in each room, built up over time from a fixed camera. */
import { useState, type ChangeEvent } from 'react';
import { deleteRoomFall, putRoomPhoto } from '../api/client';
import { useClipList } from '../hooks/useClips';
import { useDangerZone, useRoomSummaries } from '../hooks/useDangerZone';
import { ZoneMap } from '../components/ZoneMap';
import { personName } from '../lib/people';
import { LANDING_RGB, ONSET_RGB, type Layer } from '../lib/zone';
import type { DangerZone } from '../types';
import { ROOMS } from './data';
import { Icon, Modal } from './ui';
import './zones.css';

const LAYERS: { id: Layer; label: string }[] = [
  { id: 'onset', label: 'Where it began' }, { id: 'landing', label: 'Where they landed' }, { id: 'both', label: 'Both' },
];
const FEW_FALLS = 5;

const percent = (value: number) => `${Math.round(value * 100)}%`;

function download(name: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type: 'text/csv' }));
  const link = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportCsv(zone: DangerZone) {
  const rows = [['fall_id', 'recorded_at', 'source', 'person', 'p_fall', 'onset_x', 'onset_y', 'onset_estimated',
    'landing_x', 'landing_y', 'frame_width', 'frame_height']];
  for (const f of zone.falls) {
    rows.push([f.fall_id, f.created_at_utc, f.source_kind, f.track_id ? String(f.track_id) : '', f.confidence.toFixed(3),
      f.onset_x.toFixed(4), f.onset_y.toFixed(4), String(f.onset_estimated), f.landing_x.toFixed(4), f.landing_y.toFixed(4),
      String(f.frame_width), String(f.frame_height)]);
  }
  download(`icare-room-${zone.room}-falls.csv`, rows.map(r => r.map(v => `"${v.replace(/"/g, '""')}"`).join(',')).join('\n'));
}

export function DangerZones() {
  const summaries = useRoomSummaries();
  const [picked, setPicked] = useState<string | null>(null);
  const busiest = [...summaries].sort((a, b) => b.fall_count - a.fall_count)[0]?.room;
  const room = picked ?? busiest ?? ROOMS[0];
  const { zone, error, refresh } = useDangerZone(room);
  const { list: clips } = useClipList(10_000);
  const [layer, setLayer] = useState<Layer>('onset');
  const [picture, setPicture] = useState<string | null>(null);
  const [notice, setNotice] = useState('');
  const rooms = [...new Set([...ROOMS, ...summaries.map(s => s.room)])];
  const counts = new Map(summaries.map(s => [s.room, s.fall_count]));
  const pictureOf = (fallId: string) => clips?.clips.find(c => c.clip_id === fallId)?.snapshot_url ?? null;

  async function replacePhoto(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try { await putRoomPhoto(room, file); setNotice(''); refresh(); }
    catch (e) { setNotice(e instanceof Error ? e.message : 'The photo could not be saved.'); }
  }

  async function remove(fallId: string) {
    if (!window.confirm('Remove this fall from the danger zone? Use this for false alarms.')) return;
    try { await deleteRoomFall(room, fallId); setNotice(''); refresh(); }
    catch (e) { setNotice(e instanceof Error ? e.message : 'The fall could not be removed.'); }
  }

  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Danger zones</h2>
        <p className="p-muted">Where people fall in each room, from its fixed camera. Check the busiest spots for bumps, loose flooring or poor lighting.</p></div>
      <div className="p-filters">
        <label className="p-select"><span className="sr-only">Room</span>
          <select value={room} onChange={e => setPicked(e.target.value)}>
            {rooms.map(r => <option key={r} value={r}>Room {r}{counts.get(r) ? ` · ${counts.get(r)} fall${counts.get(r) === 1 ? '' : 's'}` : ''}</option>)}
          </select></label>
        <div className="p-seg" role="group" aria-label="Map layer">{LAYERS.map(l =>
          <button key={l.id} type="button" className="p-seg__item" data-on={layer === l.id ? 'true' : undefined}
            aria-pressed={layer === l.id} onClick={() => setLayer(l.id)}>{l.label}</button>)}</div>
      </div>
    </div>

    {error && <p className="p-error" role="alert">{error} The detector API may not be running.</p>}
    {notice && <p className="p-error" role="alert">{notice}</p>}

    <div className="p-zonegrid">
      <section className="p-card">
        <header className="p-card__head"><span>Room {room}</span>
          <span className="p-muted p-small">{zone ? `${zone.total_falls} recorded fall${zone.total_falls === 1 ? '' : 's'}` : 'Loading'}</span></header>
        {zone && <ZoneMap zone={zone} layer={layer} />}
        {zone && zone.total_falls === 0 && <p className="p-muted">No falls recorded for this room yet. Choose Room {room} when you start Live detection or analyze a video, and each fall found is added here.</p>}
        {zone && zone.total_falls > 0 && zone.total_falls < FEW_FALLS &&
          <p className="p-inline-alert"><Icon name="alert" size={16} />Only {zone.total_falls} fall{zone.total_falls === 1 ? '' : 's'} so far. A pattern needs more, so treat this as a hint, not a finding.</p>}
        <div className="p-quick p-zoneactions">
          <label className="p-btn">
            <Icon name="camera" size={16} />Replace photo
            <input type="file" accept="image/jpeg,image/png" hidden onChange={replacePhoto} />
          </label>
          <button type="button" className="p-btn" disabled={!zone || zone.falls.length === 0} onClick={() => zone && exportCsv(zone)}>
            <Icon name="download" size={16} />Export CSV</button>
        </div>
      </section>

      <section className="p-card p-zoneinfo">
        <header className="p-card__head"><span>Reading the map</span></header>
        <ul className="p-zonelegend">
          <li><i style={{ background: `rgb(${ONSET_RGB})` }} />Where the person was when the fall began</li>
          <li><i style={{ background: `rgb(${LANDING_RGB})` }} />Where they landed</li>
          <li><i className="p-zonelegend__faint" />Faint red: the start of the fall could not be worked out, so the landing point is used</li>
        </ul>
        <p className="p-muted p-small">Positions come from the fixed camera's image, not floor measurements, and are only comparable while the camera has not moved. The start of a fall is estimated from the body's movement and has not been validated against labelled data. Remove false alarms with the Remove button, or choose "False alarm" when responding to an alert.</p>
        <p className="p-muted p-small">Zone data is shared by everyone using this server and kept until removed. The room photo is the first frame found with nobody in it and can be replaced at any time.</p>
      </section>
    </div>

    {zone && zone.falls.length > 0 && <section className="p-card p-card--flush">
      <header className="p-card__head"><span>Recorded falls</span><span className="p-muted p-small">Newest first</span></header>
      <table className="p-table">
        <thead><tr><th>Recorded</th><th>Source</th><th>Person</th><th>P(Fall)</th><th>Began at</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{zone.falls.slice(0, 50).map(f => <tr key={f.fall_id}>
          <td className="num">{new Date(f.created_at_utc).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td>
          <td>{f.source_kind === 'live' ? 'Live camera' : 'Uploaded video'}</td>
          <td>{f.track_id ? personName(f.track_id) : '–'}</td>
          <td className="num">{percent(f.confidence)}</td>
          <td className="num">{percent(f.onset_x)}, {percent(f.onset_y)}{f.onset_estimated ? '' : ' (approx.)'}</td>
          <td className="p-table__act">
            {pictureOf(f.fall_id) && <button type="button" className="p-btn p-btn--sm" onClick={() => setPicture(pictureOf(f.fall_id))}><Icon name="camera" size={14} />Picture</button>}
            <button type="button" className="p-btn p-btn--sm" onClick={() => void remove(f.fall_id)}>Remove</button>
          </td>
        </tr>)}</tbody>
      </table>
    </section>}

    {picture && <Modal title="Where the fall began" onClose={() => setPicture(null)} wide>
      <img className="p-zonepicture" src={picture} alt="A frame from the fall with its location marked" />
      <p className="p-muted p-small">Pictures show people, so they are deleted with the clip after 24 hours. The position stays in the danger zone.</p>
    </Modal>}
  </div>;
}
