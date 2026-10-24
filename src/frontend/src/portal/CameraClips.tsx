/** Fall clips recorded by the real detector (live camera or uploaded video), played from the local API. */
import { useState } from 'react';
import { ClipView } from '../components/ClipView';
import { useClipList } from '../hooks/useClips';
import { personName } from '../lib/people';
import { Icon, Modal } from './ui';

const MB = 1024 * 1024;
const size = (bytes: number) => bytes >= 1024 * MB
  ? `${+(bytes / (1024 * MB)).toFixed(1)} GB`
  : `${(bytes / MB).toFixed(bytes < 10 * MB ? 1 : 0)} MB`;
const hours = (seconds: number) => `${Math.round(seconds / 3600)} h`;

export function CameraClips() {
  const { list, unavailable } = useClipList();
  const [open, setOpen] = useState<string | null>(null);
  const clips = list?.clips ?? [];

  return <section className="p-card p-card--flush" aria-label="Camera detections">
    <header className="p-card__head">
      <span>Camera detections</span>
      <span className="p-muted p-small">{list
        ? `${clips.length} clip${clips.length === 1 ? '' : 's'} · ${size(list.storage_used_bytes)} of ${size(list.storage_cap_bytes)} · kept ${hours(list.retention_seconds)}`
        : 'Real detector output'}</span>
    </header>
    {!list && unavailable
      ? <p className="p-empty">The detector API is not running, so recorded clips cannot be shown. Start it to see them here.</p>
      : !clips.length
        ? <p className="p-empty">No falls detected yet. A clip of about 4 seconds is saved for each fall found by Camera detection or an uploaded video.</p>
        : <table className="p-table">
          <thead><tr><th>Recorded</th><th>Source</th><th>Fall at</th><th>Person</th><th>P(Fall)</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>{clips.map(clip => <tr key={clip.clip_id}>
            <td className="num">{new Date(clip.created_at_utc).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
            <td>{clip.source_kind === 'live' ? 'Live camera' : 'Uploaded video'}</td>
            <td className="num">{clip.detected_at_seconds.toFixed(2)} s</td>
            <td>{clip.track_id ? personName(clip.track_id) : '–'}</td>
            <td className="num">{Math.round(clip.confidence * 100)}%</td>
            <td className="p-table__act">
              {clip.status === 'ready' && <button type="button" className="p-btn p-btn--sm" onClick={() => setOpen(clip.clip_id)}><Icon name="play" size={14} />Clip</button>}
              {clip.status === 'pending' && <span className="p-badge" data-tone="info">Saving</span>}
              {clip.status === 'failed' && <span className="p-badge" data-tone="bad" title={clip.error_message ?? undefined}>Not saved</span>}
            </td>
          </tr>)}</tbody>
        </table>}
    {open && <Modal title="Fall clip" onClose={() => setOpen(null)} wide><ClipView clipId={open} /></Modal>}
  </section>;
}
