/**
 * UploadPanel — real multipart upload to /api/v1/jobs/upload, job polling,
 * then video player + results. No Math.random(). No fake progress.
 */
import { useCallback, useRef, useState } from 'react';
import { startUploadJob } from '../api/client';
import type { Job } from '../types';
import { useJobPoller } from '../hooks/useJobPoller';
import { VideoPlayer } from './VideoPlayer';
import { ResultsPanel } from './ResultsPanel';

type Phase = 'idle' | 'uploading' | 'polling' | 'complete' | 'error';

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

export function UploadPanel() {
  const [localPhase, setPhase] = useState<Phase>('idle');
  const [fileName, setFileName] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [localError, setErrorMsg] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [videoTime, setVideoTime] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { job, result, error, retryable: retryStatus, retry, cancel, cancelling } = useJobPoller(jobId);
  const phase: Phase = jobId ? (result ? 'complete' : error ? 'error' : 'polling') : localPhase;
  const errorMsg = error ?? localError;

  const handleFile = useCallback(async (file: File) => {
    // Client-side validation (server also validates)
    if (!file.type.includes('mp4') && !file.name.toLowerCase().endsWith('.mp4')) {
      setErrorMsg('Only MP4 files are accepted.');
      setPhase('error');
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setErrorMsg(`File too large: ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum is 50 MB.`);
      setPhase('error');
      return;
    }

    setFileName(file.name);
    setJobId(null);
    setPhase('uploading');
    setErrorMsg(null);
    setVideoTime(0);

    try {
      const j = await startUploadJob(file);
      setJobId(j.job_id);
      setPhase('polling');
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string; code?: string };
      if (err.status === 503 && err.code === 'model_unavailable') {
        setErrorMsg('The inference model is not ready. The backend may still be starting.');
      } else if (err.status === 413 || err.code === 'file_too_large') {
        setErrorMsg('File rejected by server: too large (max 50 MB).');
      } else if (err.status === 400 || err.code === 'invalid_video') {
        setErrorMsg(`Invalid video: ${err.message ?? 'Content could not be validated.'}`);
      } else if (err.status === 429) {
        setErrorMsg('The demo is busy. Please try again shortly.');
      } else {
        setErrorMsg(err.message ?? 'Upload failed.');
      }
      setPhase('error');
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const handleReset = () => {
    setJobId(null);
    setErrorMsg(null);
    setFileName('');
    setVideoTime(0);
    setPhase('idle');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="upload-layout">
      <div className="upload-zone-wrapper">
        {phase === 'idle' && (
          <div
            className={`upload-zone${dragOver ? ' drag-over' : ''}`}
            id="upload-zone"
            role="region"
            aria-label="File upload drop zone"
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="upload-zone__icon" aria-hidden="true">
              <svg viewBox="0 0 64 64" fill="none">
                <circle cx="32" cy="32" r="30" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 3" />
                <path d="M32 44V28M24 36l8-8 8 8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h3 className="upload-zone__title">Drop your video here</h3>
            <p className="upload-zone__subtitle">or click to browse files</p>
            <button
              className="btn btn--primary btn--sm"
              id="upload-browse-btn"
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              Choose File
            </button>
            <input
              type="file"
              ref={fileInputRef}
              accept="video/mp4"
              style={{ display: 'none' }}
              aria-hidden="true"
              onChange={handleInputChange}
            />
          </div>
        )}

        {phase === 'uploading' && (
          <div className="job-card" id="upload-job-card">
            <div className="job-card__header">
              <span className="job-card__name" id="upload-filename">{fileName}</span>
              <span className="job-badge job-badge--running">uploading</span>
            </div>
            <p className="job-card__message">Uploading to server…</p>
          </div>
        )}

        {phase === 'polling' && (
          <div className="job-card" id="upload-job-card">
            <div className="job-card__header">
              <span className="job-card__name" id="upload-filename">{fileName}</span>
              <JobBadge state={job?.state ?? 'queued'} />
            </div>
            <div className="job-card__progress">
              <div className="job-progress-bar">
                <div
                  className="job-progress-fill"
                  style={{
                    width: job?.progress != null ? `${Math.round(job.progress * 100)}%` : '40%',
                    transition: 'width 0.4s ease',
                    // Indeterminate pulse when progress is null
                    animation: job?.progress == null ? 'progress-pulse 1.5s ease-in-out infinite' : undefined,
                  }}
                />
              </div>
              <span className="job-card__pct" id="upload-pct">
                {job?.progress != null ? `${Math.round(job.progress * 100)}%` : '—'}
              </span>
            </div>
            <p className="job-card__message" id="upload-message">
              {(!job || job.state === 'queued') && 'Queued — waiting for worker…'}
              {job?.state === 'running' && 'Running inference…'}
            </p>
          </div>
        )}

        {phase === 'polling' && (
          <button className="btn btn--outline btn--sm" onClick={() => void cancel()} disabled={cancelling}>
            {cancelling ? 'Cancelling…' : 'Cancel Analysis'}
          </button>
        )}

        {phase === 'complete' && result && (
          <div>
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
              <button className="btn btn--outline btn--sm" onClick={handleReset} id="upload-reset-btn">
                ↺ Upload Another
              </button>
            </div>
          </div>
        )}

        {phase === 'error' && (
          <div className="error-state" role="alert">
            <div className="error-state__icon">⚠</div>
            <p className="error-state__message">{errorMsg}</p>
            <button className="btn btn--outline btn--sm" onClick={() => {
              if (retryStatus && jobId) retry();
              else handleReset();
            }} id="upload-error-retry-btn">
              {retryStatus ? 'Retry Status Check' : 'Try Again'}
            </button>
          </div>
        )}
      </div>

      {/* Right column — upload info or results */}
      {phase === 'complete' && result ? (
        <ResultsPanel result={result} currentTime={videoTime} />
      ) : (
        <div className="upload-info" id="upload-limits">
          <h3 className="upload-info__title">Upload Requirements</h3>
          <ul className="upload-limits-list" role="list">
            <li>
              <span className="limits-icon" aria-hidden="true">📁</span>
              <span><strong>Format:</strong> MP4 only (content-validated, not just extension)</span>
            </li>
            <li>
              <span className="limits-icon" aria-hidden="true">📦</span>
              <span><strong>Size:</strong> Maximum 50 MB</span>
            </li>
            <li>
              <span className="limits-icon" aria-hidden="true">⏱</span>
              <span><strong>Duration:</strong> Maximum 60 seconds</span>
            </li>
            <li>
              <span className="limits-icon" aria-hidden="true">⚡</span>
              <span><strong>Concurrency:</strong> 1 active inference job</span>
            </li>
            <li>
              <span className="limits-icon" aria-hidden="true">🕐</span>
              <span><strong>Retention:</strong> Results deleted after 24 hours</span>
            </li>
          </ul>
          <div className="upload-privacy">
            <div className="upload-privacy__icon" aria-hidden="true">🔒</div>
            <div>
              <strong>No account required.</strong><br />
              Your upload is private. The server verifies session ownership — random job IDs alone are not authorization.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
