/** Plays one stored fall clip together with the timestamps it was cut around. */
import { useRef, useState } from 'react';
import { deleteClip } from '../api/client';
import { useClip } from '../hooks/useClips';
import { personName } from '../lib/people';
import type { Clip } from '../types';

const seconds = (value: number) => `${value.toFixed(2)} s`;

/** Where the detection falls in the clip, in seconds from its first frame. */
const detectionOffset = (clip: Clip): number | null =>
  clip.clip_start_seconds === null ? null : Math.max(0, clip.detected_at_seconds - clip.clip_start_seconds);

export function ClipView({ clipId, onDeleted }: { clipId: string; onDeleted?: () => void }) {
  const { clip, error } = useClip(clipId);
  const video = useRef<HTMLVideoElement>(null);
  const [playable, setPlayable] = useState(true);
  const [deleted, setDeleted] = useState(false);
  const [problem, setProblem] = useState('');

  if (deleted) return <p className="hint" role="status">Clip deleted.</p>;
  if (error) return <p className="notice notice--alert" role="alert">{error}</p>;
  if (!clip) return <p className="hint" role="status">Loading clip</p>;
  if (clip.status === 'pending') return <p className="hint" role="status">Saving the clip: capturing the moments after the fall.</p>;
  if (clip.status === 'failed' || !clip.video_url) {
    return <p className="notice" role="status">The clip could not be saved{clip.error_message ? `: ${clip.error_message}` : '.'}</p>;
  }

  const offset = detectionOffset(clip);
  const detected = clip.source_kind === 'live'
    ? `${new Date(clip.created_at_utc).toLocaleTimeString()} (camera time ${seconds(clip.detected_at_seconds)})`
    : `${seconds(clip.detected_at_seconds)} into the video`;

  async function remove() {
    try { await deleteClip(clipId); setDeleted(true); onDeleted?.(); }
    catch (e) { setProblem(e instanceof Error ? e.message : 'The clip could not be deleted.'); }
  }

  return <figure className="clip">
    {playable
      ? <video ref={video} className="clip__video" controls playsInline preload="metadata" src={clip.video_url}
          aria-label={`Fall clip, ${seconds(clip.duration_seconds ?? 0)}`} onError={() => setPlayable(false)} />
      : <p className="notice" role="alert">This browser cannot play the clip. <a href={clip.video_url} download>Download it</a> instead.</p>}
    {clip.snapshot_url && <div className="clip__snapshot">
      <img src={clip.snapshot_url} alt="A frame from the fall with the spot where it began marked in red" />
      <p className="hint">Where the fall began (red ring) and ended (orange ring). Deleted with the clip; the position stays in the room's danger zone.</p>
    </div>}
    <figcaption>
      <dl className="facts">
        {clip.room && <div><dt>Room</dt><dd>Room {clip.room}</dd></div>}
        <div><dt>Fall detected</dt><dd className="num">{detected}</dd></div>
        {clip.clip_start_seconds !== null && clip.duration_seconds !== null && <div>
          <dt>Clip covers</dt>
          <dd className="num">{clip.clip_start_seconds.toFixed(1)} to {(clip.clip_start_seconds + clip.duration_seconds).toFixed(1)} s</dd></div>}
        {clip.track_id ? <div><dt>Person</dt><dd>{personName(clip.track_id)}</dd></div> : null}
        <div><dt>P(Fall)</dt><dd className="num">{(clip.confidence * 100).toFixed(1)}%</dd></div>
        <div><dt>Kept until</dt><dd className="num">{new Date(clip.expires_at_utc).toLocaleString()}</dd></div>
      </dl>
      <div className="button-row">
        {offset !== null && <button type="button" className="button button--small" onClick={() => {
          const element = video.current;
          if (element) { element.currentTime = offset; void element.play().catch(() => undefined); }
        }}>Jump to detection ({seconds(offset)})</button>}
        <a className="button button--small" href={clip.video_url} download>Download</a>
        <button type="button" className="button button--small" onClick={() => void remove()}>Delete clip</button>
      </div>
      {problem && <p className="hint" role="alert">{problem}</p>}
    </figcaption>
  </figure>;
}
