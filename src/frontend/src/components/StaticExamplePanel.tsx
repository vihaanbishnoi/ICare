import { useEffect, useState } from 'react';
import type { Result, PublicExample } from '../types';
import { VideoPlayer } from './VideoPlayer';
import { ResultsPanel } from './ResultsPanel';

/** Deliberately illustrative fixture. Never used by live or upload inference. */
const SAMPLE: Result = {
  job_id: 'illustrative-example', duration_seconds: 8, frame_width: 640, frame_height: 360,
  model_version: null, analysis_mode: 'cached', media_url: '', poses: [], metrics: {}, reports: {},
  predictions: [0.08, 0.12, 0.24, 0.72, 0.81, 0.64, 0.29, 0.18].map((p, i) => ({
    timestamp_seconds: i, fall_probability: p,
  })),
  incidents: [{ incident_id: 'illustrative-event', job_id: 'illustrative-example', detected_at_seconds: 3,
    confidence: 0.72, status: 'detected', created_at_utc: 'Illustrative timestamp' }],
};

function publicFile(name: string) {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*\.(mp4|json|csv)$/.test(name) || name.includes('..')) {
    throw new Error('Invalid approved demo asset path.');
  }
  return `${import.meta.env.BASE_URL}demos/${name}`;
}

export function StaticExamplePanel() {
  const [examples, setExamples] = useState<PublicExample[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [videoTime, setVideoTime] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${import.meta.env.BASE_URL}demos/catalog.json`, { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error('Demo catalog is unavailable.'); return response.json(); })
      .then(catalog => setExamples(catalog.examples.filter((item: PublicExample) => item.approved === true)))
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, []);

  async function select(id: string) {
    setResult(null); setError(''); setVideoTime(0);
    const item = examples.find(example => example.id === id);
    if (!item) return;
    setLoading(true);
    try {
      const response = await fetch(publicFile(item.result));
      if (!response.ok) throw new Error('Recorded results could not be loaded.');
      const data = await response.json() as Result;
      setResult({ ...data, analysis_mode: 'cached', media_url: publicFile(item.video),
        reports: { json: publicFile(item.result), ...(item.csv ? { csv: publicFile(item.csv) } : {}) } });
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load recording.'); }
    finally { setLoading(false); }
  }

  return <div className="demo-grid">
    <div className="video-section">
      <div className="mode-notice">Static research preview · No inference runs on this website</div>
      {examples.length > 0 && <label className="recording-select">Approved recording
        <select disabled={loading} defaultValue="" onChange={e => void select(e.target.value)}>
          <option value="">Choose a recording</option>
          {examples.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>
      </label>}
      {result ? <>
        <p className="recorded-label">Recorded inference from the actual trained model · No new analysis is running</p>
        <VideoPlayer mediaUrl={result.media_url} frameWidth={result.frame_width} frameHeight={result.frame_height}
          poses={result.poses} predictions={result.predictions} incidents={result.incidents} onTimeChange={setVideoTime} />
      </> : <div className="video-placeholder blank-demo">
        <span className="blank-demo__icon" aria-hidden="true">▷</span>
        <p>Video demonstration not yet provided.</p>
        <p className="sample-label">Illustrative data—not model output.</p>
        <span>No video, person or inference result is simulated.</span>
      </div>}
      {error && <p role="status">{error} Illustrative preview remains available.</p>}
    </div>
    <ResultsPanel result={result ?? SAMPLE} currentTime={result ? videoTime : undefined} illustrative={!result} />
  </div>;
}
