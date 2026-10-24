/** Where a fall happened: the picture with the red area, and the room's danger zone so far. */
import { useState } from 'react';
import { useClip } from '../hooks/useClips';
import { useDangerZone } from '../hooks/useDangerZone';
import { personName } from '../lib/people';
import type { TrackId } from '../types';
import { ZoneMap } from './ZoneMap';

export interface FallRef { id: string; clipId?: string | null; at: number; person: TrackId }

function RoomZone({ room }: { room: string }) {
  const { zone } = useDangerZone(room, 5000);
  if (!zone || zone.total_falls === 0) return null;
  return <div className="fallpic__zone">
    <h3>Room {room}: all recorded falls</h3>
    <ZoneMap zone={zone} layer="onset" />
    <p className="hint">{zone.total_falls} fall{zone.total_falls === 1 ? '' : 's'} recorded in this room so far. The red area deepens where falls cluster, which is worth checking for bumps or other hazards.</p>
  </div>;
}

function Picture({ clipId, at, person }: { clipId: string; at: number; person: TrackId }) {
  const { clip, error } = useClip(clipId);
  const who = person ? `${personName(person)}, ` : '';
  return <div className="fallpic__body">
    {clip?.snapshot_url
      ? <img className="fallpic__image" src={clip.snapshot_url}
          alt={`A frame from the fall at ${at.toFixed(1)} seconds, with the area where it began highlighted in red`} />
      : <p className="hint" role="status">{error ?? (clip?.status === 'failed'
          ? 'No picture could be saved for this fall.'
          : 'Preparing the picture of where the fall happened.')}</p>}
    {clip?.snapshot_url && <p className="hint">{who}fall at {at.toFixed(2)} s. Red area: where the fall began. Orange area: where the person landed.
      The picture is deleted with the clip after 24 hours.</p>}
    {clip?.room && <RoomZone room={clip.room} />}
  </div>;
}

export function FallLocationPanel({ falls, newestFirst = false }: { falls: FallRef[]; newestFirst?: boolean }) {
  const [chosen, setChosen] = useState<string | null>(null);
  if (falls.length === 0) return null;
  const withClip = falls.filter(fall => fall.clipId);
  const current = withClip.find(fall => fall.id === chosen) ?? (newestFirst ? withClip[withClip.length - 1] : withClip[0]);

  return <section className="panel fallpic" aria-labelledby="fallpic-title">
    <header className="panel__header"><h2 id="fallpic-title">Where the fall happened</h2>
      <span>{falls.length === 1 ? '1 fall' : `${falls.length} falls`}</span></header>
    {withClip.length > 1 && <div className="button-row" role="group" aria-label="Choose a fall">
      {withClip.map((fall, index) => <button key={fall.id} type="button" className="button button--small"
        aria-pressed={fall.id === current?.id} onClick={() => setChosen(fall.id)}>
        Fall {index + 1} · {fall.at.toFixed(1)} s</button>)}
    </div>}
    {current?.clipId
      ? <Picture key={current.clipId} clipId={current.clipId} at={current.at} person={current.person} />
      : <p className="hint">No picture was kept for {falls.length === 1 ? 'this fall' : 'these falls'}: pictures are only made for the first few falls of a video.</p>}
  </section>;
}
