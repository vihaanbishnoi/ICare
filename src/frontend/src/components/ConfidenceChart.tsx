/** Fall-probability trace from real predictions, one line per person; an empty state when there are none. */
import type { Prediction, TrackId } from '../types';
import { byPerson, personColor, personKey, personLabel } from '../lib/people';

interface Props {
  predictions: Prediction[];
  /** Recorded incidents, in the same timeline as the predictions. */
  incidents: { track_id?: TrackId; identity?: string | null; detected_at_seconds: number }[];
  durationSeconds: number;
  /** Left edge of the time axis; recorded video starts at 0. */
  startSeconds?: number;
  currentTime?: number;
  emptyText: string;
}

const W = 640, H = 200;
const PAD_L = 36, PAD_R = 12, PAD_T = 12, PAD_B = 26;
const CW = W - PAD_L - PAD_R;
const CH = H - PAD_T - PAD_B;
const THRESHOLD = 0.5;

const toY = (p: number) => PAD_T + (1 - p) * CH;

export function ConfidenceChart({ predictions, incidents, durationSeconds, startSeconds = 0, currentTime, emptyText }: Props) {
  if (!predictions.length || durationSeconds <= 0) {
    return <div className="trace trace--empty"><p>{emptyText}</p></div>;
  }

  const start = startSeconds;
  const end = Math.max(durationSeconds, start + 1);
  const toX = (t: number) => PAD_L + ((t - start) / (end - start)) * CW;
  const people = byPerson(predictions);
  // One person keeps the theme accent; several people get their overlay colours.
  const several = people.size > 1;
  const tickCount = Math.max(1, Math.min(8, Math.floor(end - start)));
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => start + (i / tickCount) * (end - start));
  const playhead = currentTime !== undefined ? toX(Math.min(Math.max(currentTime, start), end)) : null;
  const peak = Math.max(...predictions.map(p => p.fall_probability));

  return <div className="trace">
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Fall probability over time for ${people.size === 1 ? 'one person' : `${people.size} people`}: ${predictions.length} predictions, peak ${(peak * 100).toFixed(1)}%, ${incidents.length} incidents`}>
      <rect className="trace__alert-zone" x={PAD_L} y={toY(1)} width={CW} height={toY(THRESHOLD) - toY(1)} />
      {[0, 0.25, 0.75, 1].map(v => <g key={v}>
        <line className="trace__grid" x1={PAD_L} x2={PAD_L + CW} y1={toY(v)} y2={toY(v)} />
        <text className="trace__axis" x={PAD_L - 6} y={toY(v) + 4} textAnchor="end">{v.toFixed(2)}</text>
      </g>)}
      <line className="trace__threshold" x1={PAD_L} x2={PAD_L + CW} y1={toY(THRESHOLD)} y2={toY(THRESHOLD)} />
      <text className="trace__axis trace__axis--threshold" x={PAD_L - 6} y={toY(THRESHOLD) + 4} textAnchor="end">0.50</text>
      {[...people].map(([key, series]) => {
        const line = series.map((p, i) => `${i ? 'L' : 'M'}${toX(p.timestamp_seconds).toFixed(1)},${toY(p.fall_probability).toFixed(1)}`).join(' ');
        const stroke = several ? { stroke: personColor(key) } : undefined;
        return <g key={key}>
          {!several && <path className="trace__area"
            d={`${line} L${toX(series.at(-1)!.timestamp_seconds).toFixed(1)},${toY(0)} L${toX(series[0].timestamp_seconds).toFixed(1)},${toY(0)} Z`} />}
          <path className="trace__line" d={line} style={stroke} />
          {series.map((p, i) => <circle key={i} r={2.6} style={p.fall_probability >= THRESHOLD ? undefined : stroke}
            className={p.fall_probability >= THRESHOLD ? 'trace__point trace__point--alert' : 'trace__point'}
            cx={toX(p.timestamp_seconds)} cy={toY(p.fall_probability)} />)}
        </g>;
      })}
      {incidents.filter(item => item.detected_at_seconds >= start).map((item, i) => {
        const x = toX(item.detected_at_seconds);
        return <g key={i}>
          <line className="trace__incident" x1={x} x2={x} y1={PAD_T} y2={PAD_T + CH} />
          <text className="trace__incident-label" x={x + 5} y={PAD_T + 11 + (i % 3) * 12}>
            {several ? `${personLabel(item.track_id, item.identity)} fall` : 'Fall'}
          </text>
        </g>;
      })}
      {playhead !== null && <line className="trace__playhead" x1={playhead} x2={playhead} y1={PAD_T} y2={PAD_T + CH} />}
      {ticks.map(t => <text key={t} className="trace__axis" x={toX(t)} y={H - 6} textAnchor="middle">{`${Math.round(t)} s`}</text>)}
    </svg>
    {several && <ul className="trace__legend" aria-label="People">
      {[...people.keys()].map(key => <li key={key}><span style={{ background: personColor(key) }} aria-hidden="true" />{personLabel(key, incidents.find(item => personKey(item.track_id) === key && item.identity)?.identity)}</li>)}
    </ul>}
  </div>;
}
