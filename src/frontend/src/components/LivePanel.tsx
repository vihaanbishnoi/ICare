import { useLiveCamera } from '../hooks/useLiveCamera';
import { ConfidenceChart } from './ConfidenceChart';
import { IncidentTable, Readout } from './ResultsPanel';
import { personColor, personName } from '../lib/people';

export function LivePanel() {
  const live = useLiveCamera();
  const { frame, phase, videoRef, canvasRef } = live;
  const active = phase === 'starting' || phase === 'running';
  // Highest current reading among people in view, each from their own latest window.
  const lastByPerson = new Map<number, number>();
  for (const p of live.predictions) lastByPerson.set(p.track_id ?? 0, p.fall_probability);
  const inView = frame?.people ?? [];
  const current = inView.filter(person => person.status === 'monitoring' && lastByPerson.has(person.track_id))
    .map(person => ({ track_id: person.track_id, p: lastByPerson.get(person.track_id)! }))
    .sort((a, b) => b.p - a.p)[0] ?? null;
  const status = phase === 'running' ? frame?.incident_latched ? 'Incident recorded, waiting to re-arm'
    : frame?.status === 'monitoring' ? (inView.length > 1 ? `Monitoring ${inView.length} people` : 'Monitoring')
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
      Fall incident recorded. That person's further alerts are held until three of their predictions fall below 0.35; everyone else is still monitored. This does not mean the person has recovered.
    </div>}
    {active && frame?.status === 'warming_up' && <p className="notice">
      Collecting continuous poses. Predictions start for each person after six of their poses spanning two seconds; gaps over one second restart their count.
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
          <ConfidenceChart predictions={live.predictions} incidents={live.incidents}
            durationSeconds={Math.max(now, 4)} startSeconds={Math.max(0, (live.predictions[0]?.timestamp_seconds ?? 0) - 1)}
            currentTime={showFrame ? now : undefined}
            emptyText="The trace starts once enough continuous poses have been collected." />
        </section>
      </div>

      <aside className="workspace__side" aria-label="Live session details">
        <Readout label="Current P(Fall)" value={active && current ? current.p : null}
          note={active && current && inView.length > 1 ? `Highest of ${inView.length} people: ${personName(current.track_id)}.` : 'An incident opens at 0.50 or above.'} />
        <section className="side-block">
          <h2>People in view</h2>
          {!active || inView.length === 0
            ? <p className="hint">{active ? 'Nobody detected in the latest frame.' : 'Each person is tracked separately once the camera starts.'}</p>
            : <ul className="people">{inView.map(person => <li key={person.track_id} data-alert={person.incident_latched ? 'true' : undefined}>
                <span><span className="person-dot" style={{ background: personColor(person.track_id) }} aria-hidden="true" />{personName(person.track_id)}</span>
                <span className="num">{person.incident_latched ? 'Fall recorded'
                  : person.status === 'monitoring' ? (lastByPerson.has(person.track_id) ? `${(lastByPerson.get(person.track_id)! * 100).toFixed(1)}%` : 'Monitoring')
                  : `Collecting ${person.coverage_seconds.toFixed(1)} / 2 s`}</span>
              </li>)}</ul>}
        </section>
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
              id: item.incident_id, person: item.track_id, when: new Date(item.created_at_utc).toLocaleTimeString(),
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
                  id: item.incident_id, person: item.track_id, when: new Date(item.created_at_utc).toLocaleTimeString(),
                  at: item.detected_at_seconds, confidence: item.confidence }))} />}
                <p className="provenance">{session.model_version}</p>
              </details>
            </li>)}</ul>}
        </section>
      </aside>
    </div>
  </div>;
}
