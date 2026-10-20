/** Result details from real API data; nothing here is computed beyond simple summaries. */
import type { Result } from '../types';

const pct = (value: number) => `${(value * 100).toFixed(1)}%`;

/** The single large reading in a side column. */
export function Readout({ label, value, note }: { label: string; value: number | null; note: string }) {
  return <section className="readout" data-alert={value !== null && value >= 0.5 ? 'true' : undefined}>
    <h2>{label}</h2>
    <p className="readout__value num">{value === null ? '—' : pct(value)}</p>
    <p className="hint">{note}</p>
  </section>;
}

interface IncidentRow { id: string; when?: string; at: number; confidence: number }

export function IncidentTable({ rows }: { rows: IncidentRow[] }) {
  const clock = rows.some(row => row.when);
  return <table className="incidents">
    <thead><tr>{clock && <th scope="col">Time</th>}<th scope="col">At</th><th scope="col">P(Fall)</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.id}>
      {clock && <td>{row.when}</td>}
      <td className="num">{row.at.toFixed(2)} s</td>
      <td className="num">{pct(row.confidence)}</td>
    </tr>)}</tbody>
  </table>;
}

export function ResultsSide({ result }: { result: Result }) {
  const peak = result.predictions.length ? Math.max(...result.predictions.map(p => p.fall_probability)) : null;
  const times = result.predictions.map(p => p.inference_ms).filter((v): v is number => typeof v === 'number');
  const meanMs = times.length ? times.reduce((a, b) => a + b, 0) / times.length : null;

  return <>
    <Readout label="Peak P(Fall)" value={peak} note="Highest prediction in this video. Incidents open at 0.50 or above." />
    <section className="side-block">
      <h2>{result.incidents.length === 1 ? '1 incident' : `${result.incidents.length} incidents`}</h2>
      {result.incidents.length === 0
        ? <p className="hint">No prediction reached the 0.50 threshold.</p>
        : <IncidentTable rows={result.incidents.map(item => ({ id: item.incident_id, at: item.detected_at_seconds, confidence: item.confidence }))} />}
    </section>
    <section className="side-block">
      <h2>Summary</h2>
      <dl className="facts">
        <div><dt>Video length</dt><dd className="num">{result.duration_seconds.toFixed(2)} s</dd></div>
        <div><dt>Predictions</dt><dd className="num">{result.predictions.length}</dd></div>
        <div><dt>Mean PoseC3D time</dt><dd className="num">{meanMs === null ? 'Not measured' : `${meanMs.toFixed(0)} ms`}</dd></div>
      </dl>
      <p className="provenance">{result.model_version ?? 'Model version not reported'}</p>
    </section>
    {(result.reports.json || result.reports.csv) && <section className="side-block">
      <h2>Reports</h2>
      <div className="button-row">
        {result.reports.json && <a className="button button--small" href={result.reports.json} download>Download JSON</a>}
        {result.reports.csv && <a className="button button--small" href={result.reports.csv} download>Download CSV</a>}
      </div>
    </section>}
  </>;
}
