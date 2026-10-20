import { useLiveCamera } from '../hooks/useLiveCamera';
import { ConfidenceChart } from './ConfidenceChart';
import { IncidentTable, Readout } from './ResultsPanel';

export function LivePanel() {
  const live = useLiveCamera();
  const { frame, phase, videoRef, canvasRef } = live;
  const active = phase === 'starting' || phase === 'running';
  const latest = live.predictions.at(-1);
  const currentPrediction = frame && frame.status === 'monitoring' && latest
    && frame.timestamp_seconds - latest.timestamp_seconds <= 1.5 ? latest : null;
  const status = phase === 'running' ? frame?.incident_latched ? 'Incident recorded, waiting to re-arm'
    : frame?.status === 'monitoring' ? 'Monitoring'
    : frame?.status === 'no_person' ? 'No person detected' : 'Collecting motion history'
    : phase === 'starting' ? 'Starting camera and inference' : phase === 'stopping' ? 'Stopping' : 'Camera off';
  const signal = phase === 'running' ? frame?.incident_latched ? 'alert' : 'on' : 'off';
  const showFrame = active && !!frame;
  const now = frame?.timestamp_seconds ?? 0;

  return <div className="mode">
    <div className="controlbar">
      <div className="controlbar__status">
        <span className="signal" data-state={signal} aria-hidden="true" />
        <div>
          <strong role="status">{status}</strong>
          <p>Runs on this computer's CPU. Camera images are never saved.</p>
        </div>
      </div>
      <div className="controlbar__actions">
        <button type="button" className="button button--primary" onClick={() => void live.start()} disabled={active || phase === 'stopping'}>Start live detection</button>
        <button type="button" className="button" onClick={() => void live.stop()} disabled={!active}>Stop</button>
      </div>
    </div>

    {live.error && <div className="notice notice--alert" role="alert">{live.error}</div>}
    {active && frame?.incident_latched && <div className="notice notice--alert" role="alert">
      Fall incident recorded. Further alerts are held until three consecutive predictions fall below 0.35. This does not mean the person has recovered.
    </div>}
    {active && frame?.status === 'warming_up' && <p className="notice">
      Collecting continuous poses: {frame.pose_count} across {frame.coverage_seconds.toFixed(2)} s. Predictions start after six poses spanning two seconds; gaps over one second restart the count.
    </p>}

    <div className="workspace">
      <div className="workspace__main">
        <figure className="stage" data-alert={active && frame?.incident_latched ? 'true' : undefined}>
          <canvas ref={canvasRef} className="stage__media" width={640} height={360} hidden={!showFrame}
            aria-label="Analyzed camera frame with its pose overlay" />
          {!showFrame && <div className="stage__empty">
            <p>{active ? 'Waiting for the first analyzed frame' : 'Start live detection to analyze camera frames'}</p>
            <span>Each skeleton is drawn on the exact frame it was computed from.</span>
          </div>}
          <figcaption className="stage__caption">
            <span>Analyzed frame</span>
            <span className="num">{showFrame ? `${frame.timestamp_seconds.toFixed(2)} s` : ''}</span>
          </figcaption>
        </figure>
        <section className="panel" aria-labelledby="live-trace-title">
          <header className="panel__header"><h2 id="live-trace-title">Fall probability</h2><span>Latest 120 predictions</span></header>
          <ConfidenceChart predictions={live.predictions} incidentTimes={live.incidents.map(item => item.detected_at_seconds)}
            durationSeconds={Math.max(now, 4)} startSeconds={Math.max(0, (live.predictions[0]?.timestamp_seconds ?? 0) - 1)}
            currentTime={showFrame ? now : undefined}
            emptyText="The trace starts once enough continuous poses have been collected." />
        </section>
      </div>

      <aside className="workspace__side" aria-label="Live session details">
        <Readout label="Current P(Fall)" value={active && currentPrediction ? currentPrediction.fall_probability : null}
          note="An incident opens at 0.50 or above." />
        <section className="side-block">
          <h2>Camera preview</h2>
          <video ref={videoRef} className="preview-video" autoPlay muted playsInline aria-label="Live camera preview, not analyzed" />
          <p className="hint">Unprocessed. Stays smooth while the latest frame is being analyzed.</p>
        </section>
        <section className="side-block">
          <h2>Session measurements</h2>
          <dl className="facts">
            <div><dt>Frames completed per second</dt><dd className="num">{frame && frame.frames_processed >= 3 ? frame.processed_fps.toFixed(2) : active ? 'Measuring' : '—'}</dd></div>
            <div><dt>Backend processing</dt><dd className="num">{frame ? `${frame.processing_ms.toFixed(0)} ms` : '—'}</dd></div>
            <div><dt>Capture to result</dt><dd className="num">{live.roundTrip !== null ? `${live.roundTrip.toFixed(0)} ms` : '—'}</dd></div>
          </dl>
        </section>
        <section className="side-block">
          <div className="side-block__header">
            <h2>Incident history</h2>
            <button type="button" className="button button--small" onClick={() => void live.refreshHistory()}>Refresh</button>
          </div>
          <p className="hint">Private to this browser session. Only times and probabilities are kept, no video.</p>
          {live.incidents.length > 0 && <>
            <h3>This session</h3>
            <IncidentTable rows={live.incidents.map(item => ({
              id: item.incident_id, when: new Date(item.created_at_utc).toLocaleTimeString(),
              at: item.detected_at_seconds, confidence: item.confidence }))} />
          </>}
          {live.history.length === 0
            ? <p className="hint">No earlier camera sessions.</p>
            : <ul className="sessions">{live.history.map(session => <li key={session.session_id}>
              <details>
                <summary>
                  <span>{new Date(session.created_at_utc).toLocaleString()}</span>
                  <span>{session.incidents.length === 1 ? '1 incident' : `${session.incidents.length} incidents`}, {session.state}</span>
                </summary>
                {session.error_message && <p className="hint">{session.error_message}</p>}
                {session.incidents.length > 0 && <IncidentTable rows={session.incidents.map(item => ({
                  id: item.incident_id, when: new Date(item.created_at_utc).toLocaleTimeString(),
                  at: item.detected_at_seconds, confidence: item.confidence }))} />}
                <p className="provenance">{session.model_version}</p>
              </details>
            </li>)}</ul>}
        </section>
      </aside>
    </div>
  </div>;
}
