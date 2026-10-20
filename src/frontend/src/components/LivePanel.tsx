import { useLiveCamera } from '../hooks/useLiveCamera';
import { ConfidenceChart } from './ConfidenceChart';

export function LivePanel() {
  const live = useLiveCamera();
  const { frame, phase, videoRef, canvasRef } = live;
  const active = phase === 'starting' || phase === 'running';
  const latest = live.predictions.at(-1);
  const currentPrediction = frame && frame.status === 'monitoring' && latest
    && frame.timestamp_seconds - latest.timestamp_seconds <= 1.5 ? latest : null;
  const status = phase === 'running' ? frame?.incident_latched ? 'Incident recorded · waiting to re-arm'
    : frame?.status === 'monitoring' ? 'Monitoring'
    : frame?.status === 'no_person' ? 'No person detected' : 'Collecting motion history'
    : phase === 'starting' ? 'Starting camera and inference' : phase === 'stopping' ? 'Stopping' : 'Camera stopped';
  const chartIncidents = live.incidents.map(item => ({ ...item, job_id: item.session_id, status: 'detected' as const }));

  return <div className="live-dashboard">
    <div className="live-toolbar">
      <div><span className={`status-dot${phase === 'running' ? ' status-dot--on' : ''}`} />
        <strong role="status">{status}</strong>
        <p>Local CPU inference · Camera images are not saved</p></div>
      <div className="live-controls">
        <button className="btn btn--primary" onClick={() => void live.start()} disabled={active || phase === 'stopping'}>Start Live Detection</button>
        <button className="btn btn--outline" onClick={() => void live.stop()} disabled={!active}>Stop Detection</button>
      </div>
    </div>
    {live.error && <div className="camera-error" role="alert">{live.error}</div>}
    <div className="live-grid">
      <div className={`camera-card${active && frame?.incident_latched ? ' camera-card--alert' : ''}`}>
        <div className="card__header"><h3>Analyzed frame + skeleton</h3>
          <span>{active && frame ? `${frame.timestamp_seconds.toFixed(2)} s capture` : 'Waiting for camera'}</span></div>
        <canvas ref={canvasRef} className={`processed-camera${!active || !frame ? ' processed-camera--empty' : ''}`}
          width={640} height={360} aria-label="Exact analyzed camera frame with synchronized pose overlay" />
        {(!active || !frame) && <p className="camera-empty">Start the camera to inspect real inference results.</p>}
        <p className="camera-caption">Each skeleton is drawn on its original captured frame. Processing delay is measured below.</p>
      </div>
      <div className="camera-card camera-preview">
        <div className="card__header"><h3>Live camera preview</h3><span>Unprocessed</span></div>
        <video ref={videoRef} autoPlay muted playsInline aria-label="Live webcam preview" />
        <p className="camera-caption">Preview stays responsive while the latest submitted frame is analyzed.</p>
      </div>
    </div>
    <div className="live-stat-grid" aria-label="Measured session performance">
      <div><span>Current P(Fall)</span><strong>{active && currentPrediction ? `${(currentPrediction.fall_probability * 100).toFixed(1)}%` : '—'}</strong></div>
      <div><span>Completed frames / session second</span><strong>{frame && frame.frames_processed >= 3 ? frame.processed_fps.toFixed(2) : 'Measuring…'}</strong></div>
      <div><span>Last backend processing</span><strong>{frame ? `${frame.processing_ms.toFixed(0)} ms` : '—'}</strong></div>
      <div><span>Last capture-to-result</span><strong>{live.roundTrip !== null ? `${live.roundTrip.toFixed(0)} ms` : '—'}</strong></div>
    </div>
    {active && frame?.status === 'warming_up' && <p className="mode-notice">Collecting continuous poses: {frame.pose_count} poses across {frame.coverage_seconds.toFixed(2)} s. Gaps reset temporal coverage.</p>}
    {active && frame?.incident_latched && <div className="live-alert" role="alert">Fall incident recorded. Further alerts are suppressed until three consecutive predictions below 0.35. This does not establish recovery.</div>}
    <div className="card"><div className="card__header"><h3>Current session confidence</h3><span>Latest 120 predictions</span></div>
      <ConfidenceChart predictions={live.predictions} incidents={chartIncidents} durationSeconds={Math.max(frame?.timestamp_seconds ?? 0, 4)} currentTime={frame?.timestamp_seconds} />
    </div>
    <div className="card history-card"><div className="card__header"><h3>Incident history</h3>
      <button className="btn btn--outline btn--sm" onClick={() => void live.refreshHistory()}>Refresh history</button></div>
      <p>Private to this browser session · Retained according to local API settings · No camera recordings</p>
      {live.incidents.length > 0 && <div className="current-incidents">
        <h4>Current session</h4>{live.incidents.map(item => <p key={item.incident_id}>
          {new Date(item.created_at_utc).toLocaleString()} · Capture {item.detected_at_seconds.toFixed(2)} s · P(Fall) {(item.confidence * 100).toFixed(1)}%
        </p>)}
      </div>}
      {live.history.length === 0 ? <p>No previous camera sessions recorded.</p> : live.history.map(session => <details key={session.session_id}>
        <summary>{new Date(session.created_at_utc).toLocaleString()} · {session.state} · {session.incidents.length} incidents</summary>
        <p className="model-provenance">{session.model_version}</p>
        {session.error_message && <p>{session.error_message}</p>}
        {session.incidents.length === 0 ? <p>No incidents recorded.</p> : session.incidents.map(item => <p key={item.incident_id}>
          {new Date(item.created_at_utc).toLocaleTimeString()} · Capture {item.detected_at_seconds.toFixed(2)} s · P(Fall) {(item.confidence * 100).toFixed(1)}%
        </p>)}
      </details>)}
    </div>
  </div>;
}
