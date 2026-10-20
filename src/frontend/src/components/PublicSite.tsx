/** GitHub Pages build: a recorded demonstration and how ICare works. No camera, uploads or inference. */
import { Brand, ThemeToggle } from './Chrome';
import { HAS_DEMO_VIDEO } from '../config';

const REPOSITORY = 'https://github.com/vihaanbishnoi/ICare';

const STEPS = [
  ['Sample frames', 'Recorded videos are sampled six times per source second. The camera sends at most six frames per second and skips stale frames while inference is busy.'],
  ['Find the person and joints', 'One YOLO26n-pose pass detects people and estimates 17 COCO joints together. The largest visible person is followed.'],
  ['Map back to the source', 'Boxes and joints are mapped from the 640-pixel model input back to the original frame, so overlays line up with the video.'],
  ['Build the motion window', 'Up to four seconds of poses are resampled to 48 positions and drawn as 17 × 48 × 64 × 64 joint heatmaps.'],
  ['Classify the movement', 'PoseC3D returns the probability of a fall. An incident opens at 0.50 and re-arms after three predictions below 0.35.'],
];

const METRICS = ['Accuracy', 'Precision', 'Recall', 'F1 score', 'Detection latency', 'Throughput'];

function Demonstration() {
  return <figure className="demo">
    <figcaption className="demo__label">Recorded demonstration</figcaption>
    {HAS_DEMO_VIDEO
      ? <video className="demo__video" src={`${import.meta.env.BASE_URL}demo.mp4`} controls playsInline preload="metadata">
          Your browser cannot play this video.
        </video>
      : <div className="demo__video demo__video--pending"><p>Demo recording coming soon.</p></div>}
  </figure>;
}

export function PublicSite() {
  return <>
    <header className="topbar">
      <div className="topbar__inner">
        <Brand />
        <nav className="topbar__links" aria-label="Sections">
          <a href="#demo">Demo</a>
          <a href="#how-it-works">How it works</a>
          <a href="#evaluation">Evaluation</a>
        </nav>
        <div className="topbar__end">
          <a className="button button--small" href={REPOSITORY} target="_blank" rel="noopener noreferrer">GitHub</a>
          <ThemeToggle />
        </div>
      </div>
    </header>
    <main className="page page--site">
      <section className="hero" aria-labelledby="site-title">
        <h1 id="site-title">ICare</h1>
        <p className="hero__lead">Pose-based fall detection with local CPU inference and a React dashboard.</p>
        <p className="hero__body">ICare combines YOLO26n-pose and PoseC3D to estimate fall probability from body movement over time.</p>
        <div className="button-row hero__actions">
          <a className="button button--primary" href={`${REPOSITORY}#run-locally`} target="_blank" rel="noopener noreferrer">Run it locally</a>
          <a className="button" href={REPOSITORY} target="_blank" rel="noopener noreferrer">View source</a>
        </div>
      </section>

      <section id="demo" className="section" aria-label="Recorded demonstration">
        <Demonstration />
      </section>

      <section id="how-it-works" className="section" aria-labelledby="how-title">
        <h2 id="how-title">How it works</h2>
        <ol className="steps">{STEPS.map(([title, body]) => <li key={title}><h3>{title}</h3><p>{body}</p></li>)}</ol>
        <p className="hint section__note">The re-arm rule only suppresses repeated alerts; it does not establish that a person recovered.
          Model inference time is not end-to-end alert latency.</p>
      </section>

      <section id="evaluation" className="section" aria-labelledby="evaluation-title">
        <h2 id="evaluation-title">Evaluation status</h2>
        <p className="section__note">The current YOLO26n-pose and PoseC3D combination has not been evaluated on labelled videos.
          Earlier classifier results do not apply to it, so no figures are shown.</p>
        <dl className="facts facts--wide">{METRICS.map(label => <div key={label}><dt>{label}</dt><dd>Not yet evaluated</dd></div>)}</dl>
      </section>
    </main>
  </>;
}
