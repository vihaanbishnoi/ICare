/** Fall-probability trace from real predictions; an empty state when there are none. */
import type { Prediction } from '../types';

interface Props {
  predictions: Prediction[];
  /** Times of recorded incidents, in the same timeline as the predictions. */
  incidentTimes: number[];
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

export function ConfidenceChart({ predictions, incidentTimes, durationSeconds, startSeconds = 0, currentTime, emptyText }: Props) {
  if (!predictions.length || durationSeconds <= 0) {
    return <div className="trace trace--empty"><p>{emptyText}</p></div>;
  }

  const start = startSeconds;
  const end = Math.max(durationSeconds, start + 1);
  const toX = (t: number) => PAD_L + ((t - start) / (end - start)) * CW;
  const line = predictions.map((p, i) => `${i ? 'L' : 'M'}${toX(p.timestamp_seconds).toFixed(1)},${toY(p.fall_probability).toFixed(1)}`).join(' ');
  const area = `${line} L${toX(predictions.at(-1)!.timestamp_seconds).toFixed(1)},${toY(0)} L${toX(predictions[0].timestamp_seconds).toFixed(1)},${toY(0)} Z`;
  const tickCount = Math.max(1, Math.min(8, Math.floor(end - start)));
  const ticks = Array.from({ length: tickCount + 1 }, (_, i) => start + (i / tickCount) * (end - start));
  const playhead = currentTime !== undefined ? toX(Math.min(Math.max(currentTime, start), end)) : null;

  return <div className="trace">
    <svg viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Fall probability over time: ${predictions.length} predictions, peak ${(Math.max(...predictions.map(p => p.fall_probability)) * 100).toFixed(1)}%, ${incidentTimes.length} incidents`}>
      <rect className="trace__alert-zone" x={PAD_L} y={toY(1)} width={CW} height={toY(THRESHOLD) - toY(1)} />
      {[0, 0.25, 0.75, 1].map(v => <g key={v}>
        <line className="trace__grid" x1={PAD_L} x2={PAD_L + CW} y1={toY(v)} y2={toY(v)} />
        <text className="trace__axis" x={PAD_L - 6} y={toY(v) + 4} textAnchor="end">{v.toFixed(2)}</text>
      </g>)}
      <line className="trace__threshold" x1={PAD_L} x2={PAD_L + CW} y1={toY(THRESHOLD)} y2={toY(THRESHOLD)} />
      <text className="trace__axis trace__axis--threshold" x={PAD_L - 6} y={toY(THRESHOLD) + 4} textAnchor="end">0.50</text>
      <path className="trace__area" d={area} />
      <path className="trace__line" d={line} />
      {predictions.map((p, i) => <circle key={i} r={2.6}
        className={p.fall_probability >= THRESHOLD ? 'trace__point trace__point--alert' : 'trace__point'}
        cx={toX(p.timestamp_seconds)} cy={toY(p.fall_probability)} />)}
      {incidentTimes.filter(t => t >= start).map((t, i) => <g key={i}>
        <line className="trace__incident" x1={toX(t)} x2={toX(t)} y1={PAD_T} y2={PAD_T + CH} />
        <text className="trace__incident-label" x={toX(t) + 5} y={PAD_T + 11}>Fall</text>
      </g>)}
      {playhead !== null && <line className="trace__playhead" x1={playhead} x2={playhead} y1={PAD_T} y2={PAD_T + CH} />}
      {ticks.map(t => <text key={t} className="trace__axis" x={toX(t)} y={H - 6} textAnchor="middle">{`${Math.round(t)} s`}</text>)}
    </svg>
  </div>;
}
