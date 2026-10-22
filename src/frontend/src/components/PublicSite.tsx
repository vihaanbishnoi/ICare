/** Static showcase of the earlier fall-detection iteration. */
import { Brand, ThemeToggle } from './Chrome';

const REPOSITORY = 'https://github.com/vihaanbishnoi/ICare';
const STEPS = [
  ['Detect the person', 'YOLO Tiny locates the person in the video.'],
  ['Estimate the pose', 'RTMPose estimates body joints to represent posture and movement.'],
  ['Recognize a fall', 'The fall-detection pipeline uses movement over time to identify falls.'],
];

export function PublicSite() {
  return <>
    <header className="topbar">
      <div className="topbar__inner">
        <Brand />
        <nav className="topbar__links" aria-label="Sections">
          <a href="#demo">Demo</a>
          <a href="#how-it-works">How it works</a>
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
        <p className="hero__lead">Recognizing falls through human movement.</p>
        <p className="hero__body">A recorded demonstration of pose-based fall detection, using YOLO Tiny for person detection and RTMPose for pose estimation.</p>
        <div className="button-row hero__actions">
          <a className="button button--primary" href="#demo">Watch the demo</a>
          <a className="button" href={REPOSITORY} target="_blank" rel="noopener noreferrer">View project</a>
        </div>
      </section>

      <section id="demo" className="section" aria-label="Recorded demonstration">
        <figure className="demo">
          <figcaption className="demo__label">Fall detection · Recorded demo</figcaption>
          <video className="demo__video" src={`${import.meta.env.BASE_URL}demo.mp4`} controls playsInline preload="metadata" aria-label="Fall Detection Testing demo" aria-describedby="demo-context">
            Your browser cannot play this video. <a href={`${import.meta.env.BASE_URL}demo.mp4`}>Download the demo</a>.
          </video>
          <p id="demo-context" className="section__note">This recording shows the earlier YOLO Tiny + RTMPose iteration of ICare. The repository also contains the newer local application.</p>
        </figure>
      </section>

      <section id="how-it-works" className="section" aria-labelledby="how-title">
        <h2 id="how-title">From video to movement</h2>
        <ol className="steps steps--demo">{STEPS.map(([title, body]) => <li key={title}><h3>{title}</h3><p>{body}</p></li>)}</ol>
      </section>
    </main>
  </>;
}
