/**
 * ConfidenceChart — SVG timeline built from real predictions[].
 * No invented values. Falls back to empty state when no predictions yet.
 */
import type { Incident, Prediction } from '../types';

interface Props {
  predictions: Prediction[];
  incidents: Incident[];
  durationSeconds: number;
  currentTime?: number;  // for live playhead sync (optional)
}

const W = 600, H = 160;
const PAD_L = 32, PAD_R = 12, PAD_T = 14, PAD_B = 28;
const CW = W - PAD_L - PAD_R;
const CH = H - PAD_T - PAD_B;

function toX(t: number, dur: number) { return PAD_L + (t / dur) * CW; }
function toY(p: number) { return PAD_T + (1 - p) * CH; }
function fmtT(s: number) { return `${Math.floor(s)}s`; }

export function ConfidenceChart({ predictions, incidents, durationSeconds, currentTime }: Props) {
  if (!predictions.length || durationSeconds <= 0) {
    return (
      <div className="chart-empty" aria-label="No prediction data yet">
        <span className="chart-empty__icon">📊</span>
        <span>Predictions will appear here when inference is complete.</span>
      </div>
    );
  }

  const dur = durationSeconds;
  const pts = predictions.map(p => ({ x: toX(p.timestamp_seconds, dur), y: toY(p.fall_probability), p: p.fall_probability }));
  const lineD = pts.map((pt, i) => `${i === 0 ? 'M' : 'L'}${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(' ');
  const areaD = lineD + ` L${pts[pts.length - 1].x.toFixed(1)},${toY(0)} L${PAD_L},${toY(0)} Z`;

  // Tick labels along X axis
  const tickCount = Math.min(8, Math.ceil(dur));
  const ticks: number[] = [];
  for (let i = 0; i <= tickCount; i++) ticks.push((i / tickCount) * dur);

  const playheadX = currentTime !== undefined ? toX(Math.min(currentTime, dur), dur) : null;

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label="Fall probability over time"
      className="confidence-chart"
      style={{ width: '100%', height: 'auto' }}
    >
      <defs>
        <linearGradient id="grad-safe" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3fb950" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#3fb950" stopOpacity="0.02" />
        </linearGradient>
        <linearGradient id="grad-danger" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#f85149" stopOpacity="0.36" />
          <stop offset="100%" stopColor="#f85149" stopOpacity="0.03" />
        </linearGradient>
        <clipPath id="clip-above">
          <rect x={PAD_L} y={PAD_T} width={CW} height={toY(0.5) - PAD_T} />
        </clipPath>
        <clipPath id="clip-below">
          <rect x={PAD_L} y={toY(0.5)} width={CW} height={CH - (toY(0.5) - PAD_T)} />
        </clipPath>
      </defs>

      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1.0].map(v => (
        <g key={v}>
          <line
            x1={PAD_L} y1={toY(v)} x2={PAD_L + CW} y2={toY(v)}
            stroke={v === 0.5 ? 'rgba(248,81,73,0.35)' : 'rgba(139,148,158,0.08)'}
            strokeWidth={v === 0.5 ? 1.5 : 1}
            strokeDasharray={v === 0.5 ? '4,3' : undefined}
          />
          <text x={PAD_L - 4} y={toY(v) + 4} textAnchor="end" fill="rgba(139,148,158,0.5)" fontSize={9} fontFamily="'JetBrains Mono',monospace">
            {v.toFixed(2)}
          </text>
        </g>
      ))}

      {/* Area fills */}
      <path d={areaD} fill="url(#grad-safe)" clipPath="url(#clip-below)" />
      <path d={areaD} fill="url(#grad-danger)" clipPath="url(#clip-above)" />

      {/* Line */}
      <path d={lineD} fill="none" stroke="#58a6ff" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

      {/* Dots */}
      {predictions.map((pred, i) => (
        <circle
          key={i}
          cx={toX(pred.timestamp_seconds, dur).toFixed(1)}
          cy={toY(pred.fall_probability).toFixed(1)}
          r={3.5}
          fill={pred.fall_probability >= 0.5 ? '#f87171' : '#34d399'}
          stroke="rgba(7,12,22,0.6)"
          strokeWidth={1.5}
        />
      ))}

      {/* Incident markers */}
      {incidents.map(inc => {
        const x = toX(inc.detected_at_seconds, dur);
        return (
          <g key={inc.incident_id}>
            <line x1={x} y1={PAD_T} x2={x} y2={PAD_T + CH} stroke="rgba(248,113,113,0.5)" strokeWidth={1.5} strokeDasharray="4,3" />
            <polygon points={`${x},${PAD_T} ${x - 5},${PAD_T + 10} ${x + 5},${PAD_T + 10}`} fill="#f87171" />
            <text x={x + 6} y={PAD_T + 11} fill="#f87171" fontSize={9} fontFamily="'JetBrains Mono',monospace">FALL</text>
          </g>
        );
      })}

      {/* Threshold label */}
      <text x={PAD_L + CW - 2} y={toY(0.5) - 4} textAnchor="end" fill="rgba(248,113,113,0.6)" fontSize={9} fontFamily="'JetBrains Mono',monospace">
        threshold 0.50
      </text>

      {/* Playhead */}
      {playheadX !== null && (
        <line
          x1={playheadX} y1={PAD_T} x2={playheadX} y2={PAD_T + CH}
          stroke="rgba(34,211,238,0.7)" strokeWidth={1.5}
        />
      )}

      {/* X axis ticks */}
      {ticks.map(t => (
        <text key={t} x={toX(t, dur)} y={H - 4} textAnchor="middle" fill="rgba(139,148,158,0.5)" fontSize={9} fontFamily="'JetBrains Mono',monospace">
          {fmtT(t)}
        </text>
      ))}
    </svg>
  );
}
