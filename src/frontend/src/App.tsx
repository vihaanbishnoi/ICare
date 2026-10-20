/** Shared local dashboard and static research preview; data sources remain explicit. */
import { useEffect, useRef, useState } from 'react';
import { StaticPreviewPanel } from './components/StaticPreviewPanel';
import { UploadPanel } from './components/UploadPanel';
import { LivePanel } from './components/LivePanel';
import { STATIC_DEMO } from './config';
import './App.css';

// ─── Hero particle canvas ───────────────────────────────────────────────────

function HeroCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const particles: { x: number; y: number; vx: number; vy: number; r: number }[] = [];
    let raf = 0;
    let mouseX = -999, mouseY = -999;

    const resize = () => {
      const hero = canvas.parentElement!;
      canvas.width = hero.offsetWidth;
      canvas.height = hero.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement!);

    for (let i = 0; i < 70; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        r: Math.random() * 1.5 + 0.8,
      });
    }

    const onMouse = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    };
    document.addEventListener('mousemove', onMouse);

    const loop = () => {
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        p.x = Math.max(0, Math.min(W, p.x));
        p.y = Math.max(0, Math.min(H, p.y));
      });
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x;
          const dy = particles[i].y - particles[j].y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d < 130) {
            ctx.strokeStyle = `rgba(255,161,22,${(1 - d / 130) * 0.22})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(particles[i].x, particles[i].y);
            ctx.lineTo(particles[j].x, particles[j].y);
            ctx.stroke();
          }
        }
      }
      particles.forEach(p => {
        const dx = p.x - mouseX, dy = p.y - mouseY;
        const d = Math.sqrt(dx * dx + dy * dy);
        const alpha = d < 150 ? 0.85 - d / 150 * 0.5 : 0.3;
        ctx.fillStyle = `rgba(255,161,22,${alpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      });
      raf = requestAnimationFrame(loop);
    };
    loop();

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('mousemove', onMouse);
      ro.disconnect();
    };
  }, []);

  return <canvas ref={ref} className="hero__canvas" aria-hidden="true" />;
}

// ─── Nav ────────────────────────────────────────────────────────────────────

function Nav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  const close = () => setOpen(false);

  return (
    <nav className={`nav${scrolled ? ' scrolled' : ''}`} id="nav" role="navigation" aria-label="Main navigation">
      <div className="nav__inner">
        <a href="#" className="nav__logo" aria-label="ICare Home">
          <svg className="nav__logo-icon" viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <circle cx="16" cy="16" r="14" stroke="#ffa116" strokeWidth="2" />
            <path d="M10 16 L14 20 L22 12" stroke="#ffa116" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="16" cy="16" r="4" fill="rgba(255,161,22,0.15)" />
          </svg>
          <span className="nav__logo-text">ICare</span>
          <span className="nav__badge">Research</span>
        </a>
        <ul className="nav__links" role="list">
          <li><a href="#demo" className="nav__link">Demo</a></li>
          <li><a href="#how-it-works" className="nav__link">How It Works</a></li>
          <li><a href="#metrics" className="nav__link">Metrics</a></li>
          <li><a href="#limitations" className="nav__link">Limitations</a></li>
          <li>
            <a href="https://github.com/vihaanbishnoi/ICare" className="nav__link nav__link--cta" target="_blank" rel="noopener noreferrer">
              GitHub ↗
            </a>
          </li>
        </ul>
        <button className="nav__hamburger" id="nav-hamburger" aria-label="Toggle mobile menu" aria-expanded={open} onClick={() => setOpen(o => !o)}>
          <span /><span /><span />
        </button>
      </div>
      <div className={`nav__mobile${open ? ' open' : ''}`} id="nav-mobile" aria-hidden={!open}>
        <a href="#demo" className="nav__mobile-link" onClick={close}>Demo</a>
        <a href="#how-it-works" className="nav__mobile-link" onClick={close}>How It Works</a>
        <a href="#metrics" className="nav__mobile-link" onClick={close}>Metrics</a>
        <a href="#limitations" className="nav__mobile-link" onClick={close}>Limitations</a>
        <a href="https://github.com/vihaanbishnoi/ICare" className="nav__mobile-link" target="_blank" rel="noopener noreferrer" onClick={close}>GitHub</a>
      </div>
    </nav>
  );
}

// ─── Demo section with tabs ─────────────────────────────────────────────────

type DemoTab = 'live' | 'upload';

function DemoSection({ tab, onTabChange }: { tab: DemoTab; onTabChange: (tab: DemoTab) => void }) {
  return <section className="demo" id="demo" aria-labelledby="demo-title"><div className="container">
    <div className="section-header">
      <h2 className="section-title" id="demo-title">{STATIC_DEMO ? 'Research Demonstration' : 'Detection Dashboard'}</h2>
      <p className="section-subtitle">{STATIC_DEMO
        ? 'Explore the interface. Video recordings and validated performance results are not yet provided.'
        : 'Use your webcam or analyze a short MP4. All model inference runs on your local CPU.'}</p>
    </div>
    {STATIC_DEMO ? <StaticPreviewPanel /> : <>
      <div className="mode-notice local-mode">Local application · FastAPI and both ONNX models required · No cloud inference</div>
      <div className="tabs" role="tablist" aria-label="Detection mode">
        <button className={`tab${tab === 'live' ? ' tab--active' : ''}`} id="tab-live" role="tab"
          aria-selected={tab === 'live'} aria-controls="panel-live" onClick={() => onTabChange('live')}>Live Detection</button>
        <button className={`tab${tab === 'upload' ? ' tab--active' : ''}`} id="tab-upload" role="tab"
          aria-selected={tab === 'upload'} aria-controls="panel-upload" onClick={() => onTabChange('upload')}>Analyze Video</button>
      </div>
      <div role="tabpanel" id="panel-live" aria-labelledby="tab-live" hidden={tab !== 'live'}>
        {tab === 'live' && <LivePanel />}
      </div>
      <div role="tabpanel" id="panel-upload" aria-labelledby="tab-upload" hidden={tab !== 'upload'}>
        <UploadPanel />
      </div>
    </>}
  </div></section>;
}

// ─── How It Works ────────────────────────────────────────────────────────────
// Offline engine: 6 poses per source second, reproducible by timestamp.

function HowItWorks() {
  return (
    <section className="pipeline-section" id="how-it-works" aria-labelledby="pipeline-title">
      <div className="container">
        <div className="section-header">
          <h2 className="section-title" id="pipeline-title">How It Works</h2>
          <p className="section-subtitle">One shared inference pipeline for local camera frames and recorded videos</p>
        </div>
        <div className="pipeline" role="list" aria-label="Pipeline stages">
          <div className="pipeline-step" role="listitem">
            <div className="pipeline-step__icon" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <rect x="4" y="8" width="32" height="24" rx="3" stroke="currentColor" strokeWidth="1.5" />
                <circle cx="20" cy="20" r="6" stroke="currentColor" strokeWidth="1.5" />
                <circle cx="20" cy="20" r="3" fill="currentColor" opacity="0.4" />
              </svg>
            </div>
            <div className="pipeline-step__num" aria-hidden="true">01</div>
            <h3 className="pipeline-step__title">Frame Sampling</h3>
            <p className="pipeline-step__desc">
              Recorded videos use source timestamps. Camera capture sends at most six frames per second and skips stale frames while inference is busy.
            </p>
          </div>
          <div className="pipeline-arrow" aria-hidden="true">→</div>
          <div className="pipeline-step" role="listitem">
            <div className="pipeline-step__icon" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <rect x="6" y="6" width="28" height="28" rx="2" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 2" />
                <rect x="12" y="14" width="16" height="12" rx="1" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>
            <div className="pipeline-step__num" aria-hidden="true">02</div>
            <h3 className="pipeline-step__title">Detection &amp; Pose</h3>
            <p className="pipeline-step__desc">YOLO26n-pose detects people and estimates 17 COCO joints together in one pass, selecting the largest visible person.</p>
          </div>
          <div className="pipeline-arrow" aria-hidden="true">→</div>
          <div className="pipeline-step" role="listitem">
            <div className="pipeline-step__icon" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="10" r="3" stroke="currentColor" strokeWidth="1.5" />
                <line x1="20" y1="13" x2="20" y2="22" stroke="currentColor" strokeWidth="1.5" />
                <line x1="12" y1="17" x2="28" y2="17" stroke="currentColor" strokeWidth="1.5" />
                <line x1="20" y1="22" x2="14" y2="32" stroke="currentColor" strokeWidth="1.5" />
                <line x1="20" y1="22" x2="26" y2="32" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </div>
            <div className="pipeline-step__num" aria-hidden="true">03</div>
            <h3 className="pipeline-step__title">Coordinate Mapping</h3>
            <p className="pipeline-step__desc">Boxes and joints are mapped from the model input back to the original video for synchronized skeleton overlays.</p>
          </div>
          <div className="pipeline-arrow" aria-hidden="true">→</div>
          <div className="pipeline-step" role="listitem">
            <div className="pipeline-step__icon" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <rect x="6" y="28" width="4" height="8" rx="1" fill="currentColor" opacity="0.4" />
                <rect x="13" y="22" width="4" height="14" rx="1" fill="currentColor" opacity="0.6" />
                <rect x="20" y="16" width="4" height="20" rx="1" fill="currentColor" opacity="0.8" />
                <rect x="27" y="10" width="4" height="26" rx="1" fill="currentColor" />
                <path d="M6 26 L14 20 L22 14 L29 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <div className="pipeline-step__num" aria-hidden="true">04</div>
            <h3 className="pipeline-step__title">Temporal Buffer</h3>
            <p className="pipeline-step__desc">Rolling 4-second buffer resampled to 48 positions → 17×48×64×64 joint heatmaps.</p>
          </div>
          <div className="pipeline-arrow" aria-hidden="true">→</div>
          <div className="pipeline-step" role="listitem">
            <div className="pipeline-step__icon" aria-hidden="true">
              <svg viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="14" stroke="currentColor" strokeWidth="1.5" />
                <path d="M14 20.5 L18 24 L26 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="pipeline-step__num" aria-hidden="true">05</div>
            <h3 className="pipeline-step__title">PoseC3D ONNX</h3>
            <p className="pipeline-step__desc">Fine-tuned model outputs P(Fall), P(No Fall). Threshold 0.50 triggers incident. Re-arms after 3 predictions below 0.35.</p>
          </div>
        </div>
        <div className="pipeline-note" role="note">
          <strong>Incident rule:</strong> P(Fall) ≥ 0.50 triggers an incident. Re-arms after 3 predictions below 0.35.
          Source-video event delay requires an independent fall-onset annotation. Model inference time is not end-to-end delivery latency.
        </div>
      </div>
    </section>
  );
}

// ─── Metrics ─────────────────────────────────────────────────────────────────
// Current pipeline evaluation remains separate from measured session timings.

function Metrics() {
  return <section className="metrics-section" id="metrics" aria-labelledby="metrics-title"><div className="container">
    <div className="section-header"><h2 className="section-title" id="metrics-title">Evaluation Status</h2>
      <p className="section-subtitle">The current YOLO26n-pose + PoseC3D combination requires labelled evaluation.</p>
    </div>
    <div className="metrics-cards" role="list" aria-label="Evaluation status">
      {['Accuracy', 'Precision', 'Recall', 'F1', 'Detection latency', 'Throughput benchmark'].map(label =>
        <div className="metric-card" role="listitem" key={label}>
          <div className="metric-card__value metric-card__value--pending">Not yet evaluated</div>
          <div className="metric-card__label">{label}</div>
        </div>)}
    </div>
    <p className="evaluation-note">Historical classifier figures do not validate this updated pipeline. Local session timings are measured processing statistics, not accuracy or alert-latency benchmarks.</p>
  </div></section>;
}

// ─── Limitations ─────────────────────────────────────────────────────────────

function Limitations() {
  const items = [
    { icon: '01', title: 'One primary person', body: 'The largest visible person is analyzed. Identity tracking across multiple people is not implemented.' },
    { icon: '02', title: 'Measured CPU performance', body: 'Live throughput depends on your hardware. The camera uses the newest available frame and reports actual processing and capture-to-result timings.' },
    { icon: '03', title: 'Temporal context required', body: 'PoseC3D needs continuous motion history. Missing-person gaps reset coverage; no confidence is invented during warm-up.' },
    { icon: '04', title: 'Evaluation remains open', body: 'The pose estimator changed. The combined pipeline needs labelled evaluation before accuracy or reliability claims can be made.' },
    { icon: '05', title: 'Research prototype', body: 'Visual alerts are research outputs, not clinical assessments or an emergency response service.' },
    { icon: '06', title: 'Static public preview', body: 'The public site has no camera inference, uploads or recorded results. Run locally to analyze your own video or camera frames.' },
  ];
  return (
    <section className="limitations-section" id="limitations" aria-labelledby="limitations-title">
      <div className="container">
        <div className="section-header">
          <h2 className="section-title" id="limitations-title">Known Limitations</h2>
          <p className="section-subtitle">Honest research boundaries — read before drawing conclusions</p>
        </div>
        <div className="limitations-grid" role="list">
          {items.map(item => (
            <div className="limitation-card" role="listitem" key={item.title}>
              <div className="limitation-card__icon" aria-hidden="true">{item.icon}</div>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Footer ──────────────────────────────────────────────────────────────────

function Footer() {
  return <footer className="footer"><div className="container">
    <div className="footer__inner"><div className="footer__brand"><strong>ICare</strong>
      <p className="footer__tagline">Pose-based temporal fall detection.</p>
      <p className="footer__disclaimer">Research prototype · Not a medical device</p></div>
      <div className="footer__col"><a className="footer__link" href="#how-it-works">Architecture</a>
        <a className="footer__link" href="#metrics">Evaluation status</a>
        <a className="footer__link" href="https://github.com/vihaanbishnoi/ICare" target="_blank" rel="noopener noreferrer">Source on GitHub ↗</a>
      </div></div>
    <div className="footer__bottom"><p>{STATIC_DEMO ? 'Static preview · No backend or inference service' : 'Local application · CPU inference'}</p></div>
  </div></footer>;
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function Hero({ onNav }: { onNav: (tab: DemoTab) => void }) {
  const navigate = (tab: DemoTab) => { onNav(tab); document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); };
  return <section className="hero" id="hero" aria-labelledby="hero-title">
    <HeroCanvas /><div className="hero__gradient" aria-hidden="true" />
    <div className="hero__content"><div className="hero__eyebrow"><span className="hero__dot" />
      {STATIC_DEMO ? 'Static research demonstration' : 'Local fall-detection dashboard'}</div>
      <h1 className="hero__title" id="hero-title">Movement.<br /><span className="hero__title-gradient">In context.</span></h1>
      <p className="hero__subtitle">{STATIC_DEMO
        ? 'Explore pose-based fall detection through an interactive interface preview.'
        : 'Inspect body movement with live camera detection or recorded-video analysis.'}
        <br /><span className="hero__stack">YOLO26n-pose · PoseC3D · ONNX Runtime</span></p>
      <div className="hero__actions">{STATIC_DEMO
        ? <button className="btn btn--primary" onClick={() => navigate('live')}>Explore Demonstration</button>
        : <><button className="btn btn--primary" onClick={() => navigate('live')}>Live Detection</button>
            <button className="btn btn--outline" onClick={() => navigate('upload')}>Analyze Video</button></>}
      </div>
      <p className="hero__stats-disclaimer">{STATIC_DEMO
        ? 'No sample videos or inference results are included. Run locally to analyze your own footage.'
        : 'Runs locally on CPU. Camera access begins only when you press Start.'}</p>
    </div>
  </section>;
}

// ─── Root App ────────────────────────────────────────────────────────────────

export default function App() {
  const [demoTab, setDemoTab] = useState<DemoTab>('live');
  return <><Nav /><main><Hero onNav={setDemoTab} />
    <DemoSection tab={demoTab} onTabChange={setDemoTab} />
    <HowItWorks /><Metrics /><Limitations /></main><Footer /></>;
}
