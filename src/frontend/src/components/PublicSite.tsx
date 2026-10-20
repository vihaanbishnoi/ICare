/** GitHub Pages build: the dashboard layout with empty states. No inference, uploads or camera. */
import { useState } from 'react';
import { Brand, ModeTabs, ThemeToggle, type Mode } from './Chrome';
import { ConfidenceChart } from './ConfidenceChart';
import { Readout } from './ResultsPanel';

const REPOSITORY = 'https://github.com/vihaanbishnoi/ICare';

const STEPS = [
  ['Sample frames', 'Recorded videos are sampled six times per source second. The camera sends at most six frames per second and skips stale frames while inference is busy.'],
  ['Find the person and joints', 'One YOLO26n-pose pass detects people and estimates 17 COCO joints together. The largest visible person is followed.'],
  ['Map back to the source', 'Boxes and joints are mapped from the 640-pixel model input back to the original frame, so overlays line up with the video.'],
  ['Build the motion window', 'Up to four seconds of poses are resampled to 48 positions and drawn as 17 × 48 × 64 × 64 joint heatmaps.'],
  ['Classify the movement', 'PoseC3D returns the probability of a fall. An incident opens at 0.50 and re-arms after three predictions below 0.35.'],
];

const METRICS = ['Accuracy', 'Precision', 'Recall', 'F1 score', 'Detection latency', 'Throughput'];

function PreviewWorkspace({ mode }: { mode: Mode }) {
  return <div className="workspace">
    <div className="workspace__main">
      <figure className="stage">
        <div className="stage__empty">
          <p>{mode === 'live' ? 'No camera on this website' : 'No video on this website'}</p>
          <span>{mode === 'live'
            ? 'In the local app, analyzed camera frames appear here with their skeleton.'
            : 'In the local app, your MP4 plays back here with its skeleton overlay.'}</span>
        </div>
        <figcaption className="stage__caption"><span>{mode === 'live' ? 'Analyzed frame' : 'Video playback'}</span></figcaption>
      </figure>
      <section className="panel" aria-labelledby={`preview-trace-${mode}`}>
        <header className="panel__header"><h2 id={`preview-trace-${mode}`}>Fall probability</h2></header>
        <ConfidenceChart predictions={[]} incidentTimes={[]} durationSeconds={0}
          emptyText="The probability trace appears here after local analysis." />
      </section>
    </div>
    <aside className="workspace__side" aria-label="Preview details">
      <Readout label={mode === 'live' ? 'Current P(Fall)' : 'Peak P(Fall)'} value={null} note="An incident opens at 0.50 or above." />
      <section className="side-block">
        <h2>Incidents</h2>
        <p className="hint">None. This preview contains no recordings, predictions or incidents.</p>
      </section>
    </aside>
  </div>;
}

export function PublicSite() {
  const [mode, setMode] = useState<Mode>('live');
  return <>
    <header className="topbar">
      <Brand />
      <nav className="topbar__links" aria-label="Sections">
        <a href="#preview">Preview</a>
        <a href="#how-it-works">How it works</a>
        <a href="#evaluation">Evaluation</a>
      </nav>
      <div className="topbar__end">
        <a className="button button--small" href={REPOSITORY} target="_blank" rel="noopener noreferrer">GitHub</a>
        <ThemeToggle />
      </div>
    </header>
    <main className="page">
      <section className="intro">
        <h1>Fall detection from how the body moves over time</h1>
        <p>ICare follows a person's 17 body joints across a few seconds of video and estimates the probability of a fall.
          This page previews the interface. Inference runs only in the local app, on your own computer.</p>
      </section>

      <section id="preview" className="section" aria-labelledby="preview-title">
        <div className="section__header">
          <h2 id="preview-title">Interface preview</h2>
          <ModeTabs mode={mode} onChange={setMode} prefix="preview" label="Previewed mode" />
        </div>
        <p className="notice">Static preview: this website has no camera access, uploads or model. Run ICare locally to analyze your own camera or MP4.</p>
        <div role="tabpanel" id={`preview-panel-${mode}`} aria-labelledby={`preview-tab-${mode}`}>
          <PreviewWorkspace mode={mode} />
        </div>
      </section>

      <section id="how-it-works" className="section" aria-labelledby="how-title">
        <h2 id="how-title">How it works</h2>
        <ol className="steps">{STEPS.map(([title, body]) => <li key={title}><h3>{title}</h3><p>{body}</p></li>)}</ol>
        <p className="hint measure">The re-arm rule only suppresses repeated alerts; it does not establish that a person recovered.
          Model inference time is not end-to-end alert latency.</p>
      </section>

      <section id="evaluation" className="section" aria-labelledby="evaluation-title">
        <h2 id="evaluation-title">Evaluation status</h2>
        <p className="measure">The current YOLO26n-pose and PoseC3D combination has not been evaluated on labelled videos.
          Earlier classifier results do not apply to it, so no figures are shown.</p>
        <dl className="facts facts--wide">{METRICS.map(label => <div key={label}><dt>{label}</dt><dd>Not yet evaluated</dd></div>)}</dl>
      </section>
    </main>
    <footer className="footer">
      <p>Research prototype. Not a medical device or an emergency service.</p>
      <a href={REPOSITORY} target="_blank" rel="noopener noreferrer">Source on GitHub</a>
    </footer>
  </>;
}
