/**
 * ResultsPanel — shows ConfidenceChart, incidents, and analysis summary
 * from real Result data. No invented values.
 */
import { ConfidenceChart } from './ConfidenceChart';
import type { Incident, Prediction, Result } from '../types';

interface Props {
  result: Result;
  currentTime?: number;
}

function fmtSec(s: number) {
  return `${s.toFixed(2)} s`;
}

function fmtPct(n: number | null) {
  if (n === null) return 'n/a';
  return `${(n * 100).toFixed(1)}%`;
}

function fmtMs(n: number | null | undefined) {
  if (n === null || n === undefined) return 'n/a';
  return `${n.toFixed(0)} ms`;
}

function IncidentList({ incidents }: { incidents: Incident[] }) {
  if (incidents.length === 0) {
    return (
      <div className="incidents-empty">
        <div className="incidents-empty__icon" aria-hidden="true">✓</div>
        <div className="incidents-empty__text">
          No falls detected.<br />
          All predictions below threshold (0.50).
        </div>
      </div>
    );
  }
  return (
    <div className="incidents-list">
      {incidents.map(inc => (
        <div key={inc.incident_id} className="incident-item incident-item--danger">
          <div className="incident-icon" aria-hidden="true">⚠</div>
          <div className="incident-body">
            <div className="incident-time">
              Detected at <strong>{fmtSec(inc.detected_at_seconds)}</strong>
            </div>
            <div className="incident-conf">
              Confidence: <strong className="text-danger">{fmtPct(inc.confidence)}</strong>
            </div>
            <div className="incident-status">
              Status: <span className="status-chip status-chip--detected">{inc.status}</span>
            </div>
          </div>
          <div className="incident-label" aria-label="Fall event">FALL</div>
        </div>
      ))}
    </div>
  );
}

function peakFallProb(predictions: Prediction[]): number | null {
  if (!predictions.length) return null;
  return Math.max(...predictions.map(p => p.fall_probability));
}

function avgInferenceMs(predictions: Prediction[]): number | null {
  const times = predictions.map(p => p.inference_ms).filter((v): v is number => v !== null && v !== undefined);
  if (!times.length) return null;
  return times.reduce((a, b) => a + b, 0) / times.length;
}

export function ResultsPanel({ result, currentTime }: Props) {
  const peak = peakFallProb(result.predictions);
  const avgMs = avgInferenceMs(result.predictions);

  return (
    <div className="results-panel">
      {/* Confidence chart */}
      <div className="card" id="chart-card">
        <div className="card__header">
          <h3 className="card__title">Confidence Timeline</h3>
          <div className="legend" aria-label="Chart legend">
            <span className="legend-dot legend-dot--danger" aria-hidden="true" />
            <span className="legend-label">Fall ≥0.50</span>
            <span className="legend-dot legend-dot--safe" aria-hidden="true" />
            <span className="legend-label">Normal</span>
          </div>
        </div>
        <div className="chart-container">
          <ConfidenceChart
            predictions={result.predictions}
            incidents={result.incidents}
            durationSeconds={result.duration_seconds}
            currentTime={currentTime}
          />
        </div>
      </div>

      {/* Incident list */}
      <div className="card" id="incidents-card">
        <div className="card__header">
          <h3 className="card__title">Detected Incidents</h3>
          <span className={`badge ${result.incidents.length ? 'badge--danger' : 'badge--safe'}`}>
            {result.incidents.length} detected
          </span>
        </div>
        <IncidentList incidents={result.incidents} />
      </div>

      {/* Summary */}
      <div className="card" id="summary-card">
        <div className="card__header">
          <h3 className="card__title">Analysis Summary</h3>
        </div>
        <div className="summary-grid">
          <div className="summary-item">
            <span className="summary-label">Duration</span>
            <span className="summary-value">{fmtSec(result.duration_seconds)}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Predictions</span>
            <span className="summary-value">{result.predictions.length}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Peak P(Fall)</span>
            <span className={`summary-value ${peak !== null && peak >= 0.5 ? 'text-danger' : 'text-safe'}`}>
              {fmtPct(peak)}
            </span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Avg Inference</span>
            <span className="summary-value">{fmtMs(avgMs)}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Model</span>
            <span className="summary-value">{result.model_version ?? 'n/a'}</span>
          </div>
          <div className="summary-item">
            <span className="summary-label">Threshold</span>
            <span className="summary-value">0.50</span>
          </div>
        </div>
      </div>

      {/* Report downloads */}
      {result.reports && (
        <div className="card" id="reports-card">
          <div className="card__header">
            <h3 className="card__title">Download Reports</h3>
          </div>
          <div className="report-links">
            {result.reports.json && (
              <a href={result.reports.json} className="btn btn--outline btn--sm" download>
                ⬇ JSON Report
              </a>
            )}
            {result.reports.csv && (
              <a href={result.reports.csv} className="btn btn--outline btn--sm" download>
                ⬇ CSV Report
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
