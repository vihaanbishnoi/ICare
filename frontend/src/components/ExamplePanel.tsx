/**
 * ExamplePanel — loads example list from API, starts a job, polls, then shows results.
 * No fake upload progress. No Math.random(). No stub.
 */
import { useEffect, useState } from 'react';
import { fetchExamples, startExampleJob } from '../api/client';
import type { Example, Job } from '../types';
import { useJobPoller } from '../hooks/useJobPoller';
import { VideoPlayer } from './VideoPlayer';
import { ResultsPanel } from './ResultsPanel';

interface Props {
  initialOutcome?: 'fall' | 'no_fall';
}

type Phase = 'idle' | 'loading_examples' | 'ready' | 'submitting' | 'polling' | 'complete' | 'error';

function JobBadge({ state }: { state: Job['state'] }) {
  const cls: Record<string, string> = {
    queued: 'job-badge job-badge--queued',
    running: 'job-badge job-badge--running',
    completed: 'job-badge job-badge--completed',
    failed: 'job-badge job-badge--failed',
    cancelled: 'job-badge job-badge--failed',
  };
  return <span className={cls[state] ?? 'job-badge'}>{state}</span>;
}

function ProgressBar({ progress }: { progress: number | null }) {
  const pct = progress !== null ? Math.round(progress * 100) : null;
  return (
    <div className="job-card__progress" aria-label={`Job progress: ${pct ?? 'unknown'}%`}>
      <div className="job-progress-bar">
        <div
          className="job-progress-fill"
          style={{ width: `${pct ?? 0}%`, transition: 'width 0.4s ease' }}
        />
      </div>
      <span className="job-card__pct">{pct !== null ? `${pct}%` : '—'}</span>
    </div>
  );
}

export function ExamplePanel({ initialOutcome }: Props) {
  const [localPhase, setPhase] = useState<Phase>('loading_examples');
  const [examples, setExamples] = useState<Example[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [localError, setErrorMsg] = useState<string | null>(null);
  const [videoTime, setVideoTime] = useState(0);

  const { job, result, error, retryable: retryStatus, retry, cancel, cancelling } = useJobPoller(jobId);
  const phase: Phase = jobId ? (result ? 'complete' : error ? 'error' : 'polling') : localPhase;
  const errorMsg = error ?? localError;

  // Load examples on mount
  useEffect(() => {
    fetchExamples()
      .then(list => {
        setExamples(list);
        // Pre-select based on initialOutcome prop
        const preferred = initialOutcome
          ? list.find(e => e.expected_outcome === initialOutcome) ?? list[0]
          : list[0];
        if (preferred) setSelectedId(preferred.example_id);
        setPhase(list.length ? 'ready' : 'error');
        if (!list.length) setErrorMsg('No public examples are available yet. You can analyze your own permitted video in Upload Your Video.');
      })
      .catch(e => {
        setPhase('error');
        setErrorMsg(e instanceof Error ? e.message : 'Failed to load examples.');
      });
  }, [initialOutcome]);

  const handleRun = async () => {
    if (!selectedId) return;
    setJobId(null);
    setPhase('submitting');
    setErrorMsg(null);
    setVideoTime(0);
    try {
      const j = await startExampleJob(selectedId);
      setJobId(j.job_id);
      setPhase('polling');
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string; code?: string };
      if (err.status === 503 && err.code === 'model_unavailable') {
        setErrorMsg('The inference model is not ready. The backend may still be starting.');
      } else {
        setErrorMsg(err.message ?? 'Failed to start job.');
      }
      setPhase('error');
    }
  };

  const handleReset = () => {
    setJobId(null);
    setErrorMsg(null);
    setVideoTime(0);
    setPhase('ready');
  };

  const selectedExample = examples.find(e => e.example_id === selectedId);

  return (
    <div className="demo-grid">
      <div className="video-section">
        <div className="video-header">
          <span className="video-label">
            {selectedExample
              ? `${selectedExample.title} — ${selectedExample.expected_outcome === 'fall' ? 'Fall Example' : 'Normal Activity'}`
              : 'Example Video'}
          </span>
          {job && <JobBadge state={job.state} />}
          {phase === 'complete' && !job && <span className="job-badge job-badge--completed">✓ Completed</span>}
        </div>

        {/* Example selector */}
        {phase !== 'complete' && examples.length > 0 && (
          <div className="example-selector" style={{ marginBottom: '0.75rem' }}>
            <label htmlFor="example-select" className="example-selector__label">Select clip:</label>
            <select
              id="example-select"
              className="example-selector__select"
              value={selectedId ?? ''}
              onChange={e => setSelectedId(e.target.value)}
              disabled={phase === 'submitting' || phase === 'polling'}
            >
              {examples.map(ex => (
                <option key={ex.example_id} value={ex.example_id}>
                  {ex.title} ({ex.expected_outcome === 'fall' ? 'Fall' : 'Normal'})
                </option>
              ))}
            </select>
          </div>
        )}

        {phase === 'polling' && (
          <button className="btn btn--outline btn--sm" onClick={() => void cancel()} disabled={cancelling}>
            {cancelling ? 'Cancelling…' : 'Cancel Analysis'}
          </button>
        )}

        {/* Video player — only shown when result is ready */}
        {phase === 'complete' && result ? (
          <>
            <VideoPlayer
              mediaUrl={result.media_url}
              frameWidth={result.frame_width}
              frameHeight={result.frame_height}
              poses={result.poses}
              predictions={result.predictions}
              incidents={result.incidents}
              mode="live"
              onTimeChange={setVideoTime}
            />
            <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
              <button className="btn btn--outline btn--sm" onClick={handleReset} id="example-reset-btn">
                ↺ Run Another
              </button>
            </div>
          </>
        ) : (
          <div className="video-placeholder" aria-label="Video will appear after analysis">
            {phase === 'loading_examples' && (
              <div className="skeleton-block" style={{ height: 240, borderRadius: 8 }} aria-label="Loading examples…" />
            )}
            {(phase === 'ready' || phase === 'submitting') && (
              <div className="video-placeholder__idle">
                <div className="video-placeholder__icon">🎬</div>
                <p>Select a clip above and click <strong>Run Analysis</strong> to start inference.</p>
                {selectedExample && (
                  <p className="video-placeholder__meta">
                    {selectedExample.duration_seconds}s · {selectedExample.analysis_mode} · {selectedExample.provenance}
                  </p>
                )}
                <button
                  className="btn btn--primary"
                  onClick={handleRun}
                  disabled={phase === 'submitting' || !selectedId}
                  id="run-example-btn"
                >
                  {phase === 'submitting' ? 'Starting…' : '▶ Run Analysis'}
                </button>
              </div>
            )}
            {phase === 'polling' && job && (
              <div className="job-card" id="example-job-card">
                <div className="job-card__header">
                  <span className="job-card__name">{selectedExample?.title ?? 'Job'}</span>
                  <JobBadge state={job.state} />
                </div>
                <ProgressBar progress={job.progress} />
                <p className="job-card__message">
                  {job.state === 'queued' && 'Queued — waiting for worker…'}
                  {job.state === 'running' && 'Running inference…'}
                </p>
              </div>
            )}
            {phase === 'error' && (
              <div className="error-state" role="alert">
                <div className="error-state__icon">⚠</div>
                <p className="error-state__message">{errorMsg}</p>
                {examples.length > 0 && (
                  <button className="btn btn--outline btn--sm" onClick={() => {
                    if (retryStatus && jobId) retry();
                    else handleReset();
                  }} id="example-error-retry-btn">
                    {retryStatus ? 'Retry Status Check' : 'Try Again'}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Results panel */}
      <div className="results-panel-wrapper" id="example-results">
        {phase === 'complete' && result ? (
          <ResultsPanel result={result} currentTime={videoTime} />
        ) : (
          <div className="results-placeholder">
            <div className="results-placeholder__content">
              <div className="results-placeholder__icon">📈</div>
              <p>Inference results will appear here after analysis completes.</p>
              {phase === 'polling' && (
                <p className="results-placeholder__sub">Polling for completion…</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
