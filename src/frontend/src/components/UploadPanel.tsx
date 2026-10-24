/** Multipart upload to /api/v1/jobs/upload, job polling, then playback and results. */
import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from 'react';
import { startUploadJob } from '../api/client';
import { useJobPoller } from '../hooks/useJobPoller';
import { useRoomChoice } from '../hooks/useRoomChoice';
import { RoomPicker } from './RoomPicker';
import { ConfidenceChart } from './ConfidenceChart';
import { FallLocationPanel } from './FallLocationPanel';
import { ResultsSide } from './ResultsPanel';
import { VideoPlayer } from './VideoPlayer';

type Phase = 'idle' | 'uploading' | 'polling' | 'complete' | 'error';

const MAX_MB = 50;

export function UploadPanel() {
  const [localPhase, setPhase] = useState<Phase>('idle');
  const [fileName, setFileName] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);
  const [localError, setErrorMsg] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [videoTime, setVideoTime] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [room, setRoom] = useRoomChoice();

  const { job, result, error, retryable, retry, cancel, cancelling } = useJobPoller(jobId);
  const phase: Phase = jobId ? (result ? 'complete' : error ? 'error' : 'polling') : localPhase;
  const errorMsg = error ?? localError;

  const handleFile = useCallback(async (file: File) => {
    // The server validates content too; this only catches obvious mistakes early.
    if (!file.type.includes('mp4') && !file.name.toLowerCase().endsWith('.mp4')) {
      setErrorMsg('Only MP4 files can be analyzed. Choose an .mp4 video.');
      setPhase('error');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setErrorMsg(`This file is ${(file.size / 1024 / 1024).toFixed(1)} MB. Videos must be ${MAX_MB} MB or smaller.`);
      setPhase('error');
      return;
    }
    setFileName(file.name);
    setJobId(null);
    setPhase('uploading');
    setErrorMsg(null);
    setVideoTime(0);
    try {
      const created = await startUploadJob(file, room || undefined);
      setJobId(created.job_id);
      setPhase('polling');
    } catch (e: unknown) {
      const err = e as { status?: number; message?: string; code?: string };
      if (err.status === 503 && err.code === 'model_unavailable') {
        setErrorMsg('The models are not ready yet. Wait for the API to finish starting, then try again.');
      } else if (err.status === 413 || err.code === 'file_too_large') {
        setErrorMsg(`The server rejected the file: videos must be ${MAX_MB} MB or smaller.`);
      } else if (err.status === 400 || err.code === 'invalid_video') {
        setErrorMsg(err.message ?? 'The video could not be validated.');
      } else if (err.status === 429) {
        setErrorMsg('Another analysis is using the model. Try again when it finishes.');
      } else {
        setErrorMsg(err.message ?? 'The upload failed. Check that the API is running.');
      }
      setPhase('error');
    }
  }, [room]);

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void handleFile(file);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  }

  function reset() {
    setJobId(null);
    setErrorMsg(null);
    setFileName('');
    setVideoTime(0);
    setPhase('idle');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  const choose = () => fileInputRef.current?.click();
  const progress = job?.progress ?? null;
  const status = phase === 'idle' ? 'Ready for a video'
    : phase === 'uploading' ? 'Uploading'
    : phase === 'polling' ? (job?.state === 'running' ? 'Analyzing' : job?.state === 'completed' ? 'Loading results' : 'Queued')
    : phase === 'complete' ? 'Analysis complete' : 'Analysis stopped';

  return <div className="mode">
    <div className="controlbar">
      <div className="controlbar__status">
        <span className="signal" data-state={phase === 'polling' || phase === 'uploading' ? 'on' : phase === 'error' ? 'alert' : 'off'} aria-hidden="true" />
        <div>
          <strong role="status">{status}</strong>
          <p>{fileName || `MP4 up to ${MAX_MB} MB and 60 seconds, analyzed on this computer.`}</p>
        </div>
      </div>
      <RoomPicker value={room} onChange={setRoom} disabled={phase !== 'idle'} />
      <div className="controlbar__actions">
        {phase === 'idle' && <button type="button" className="button button--primary" onClick={choose}>Choose MP4 file</button>}
        {(phase === 'uploading' || phase === 'polling') && <button type="button" className="button" onClick={() => void cancel()}
          disabled={phase === 'uploading' || cancelling}>{cancelling ? 'Cancelling' : 'Cancel analysis'}</button>}
        {(phase === 'complete' || phase === 'error') && <button type="button" className="button button--primary" onClick={reset}>Analyze another video</button>}
      </div>
      <input type="file" ref={fileInputRef} accept="video/mp4" hidden onChange={onInputChange} />
    </div>

    <div className="workspace">
      <div className="workspace__main">
        {phase === 'idle' && <div className="stage stage--drop" data-over={dragOver ? 'true' : undefined}
          onDragOver={event => { event.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={onDrop}>
          <div className="stage__empty">
            <p>Drop an MP4 here</p>
            <span>or use Choose MP4 file. The video plays back here with its skeleton overlay.</span>
          </div>
        </div>}

        {(phase === 'uploading' || phase === 'polling') && <div className="stage">
          <div className="stage__empty">
            <p>{phase === 'uploading' ? 'Uploading the video'
              : job?.state === 'running' ? 'Running pose and fall inference'
              : job?.state === 'completed' ? 'Loading results' : 'Waiting for the model'}</p>
            <div className="progress" role="progressbar" aria-label="Analysis progress" aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={progress !== null ? Math.round(progress * 100) : undefined}>
              <div className="progress__fill" data-indeterminate={progress === null ? 'true' : undefined}
                style={{ width: progress !== null ? `${Math.round(progress * 100)}%` : undefined }} />
            </div>
            <span className="num">{progress !== null ? `${Math.round(progress * 100)}%` : 'Progress not reported yet'}</span>
          </div>
        </div>}

        {phase === 'error' && <div className="stage" role="alert">
          <div className="stage__empty">
            <p>{errorMsg}</p>
            {retryable && jobId && <button type="button" className="button" onClick={retry}>Retry status check</button>}
          </div>
        </div>}

        {phase === 'complete' && result && <>
          <VideoPlayer mediaUrl={result.media_url} frameWidth={result.frame_width} frameHeight={result.frame_height}
            poses={result.poses} predictions={result.predictions} incidents={result.incidents} onTimeChange={setVideoTime} />
          <section className="panel" aria-labelledby="video-trace-title">
            <header className="panel__header"><h2 id="video-trace-title">Fall probability</h2><span>Click play or seek to move the marker</span></header>
            <ConfidenceChart predictions={result.predictions} incidents={result.incidents}
              durationSeconds={result.duration_seconds} currentTime={videoTime}
              emptyText="No predictions: the video never had six poses spanning two seconds." />
          </section>
          <FallLocationPanel falls={result.incidents.map(item => ({
            id: item.incident_id, clipId: item.clip_id, at: item.detected_at_seconds, person: item.track_id }))} />
        </>}
      </div>

      <aside className="workspace__side" aria-label={phase === 'complete' ? 'Analysis results' : 'Upload requirements'}>
        {phase === 'complete' && result ? <ResultsSide result={result} /> : <>
          <section className="side-block">
            <h2>Requirements</h2>
            <dl className="facts">
              <div><dt>Format</dt><dd>MP4, checked by content</dd></div>
              <div><dt>Size</dt><dd>Up to {MAX_MB} MB</dd></div>
              <div><dt>Length</dt><dd>Up to 60 seconds</dd></div>
              <div><dt>Queue</dt><dd>One analysis at a time</dd></div>
              <div><dt>Retention</dt><dd>Deleted after 24 hours</dd></div>
            </dl>
          </section>
          <section className="side-block">
            <h2>Privacy</h2>
            <p className="hint">No account is needed. Uploads and results belong to this browser session; the server checks ownership on every request.</p>
          </section>
        </>}
      </aside>
    </div>
  </div>;
}
