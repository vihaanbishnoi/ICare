/**
 * ICare Frontend — App.tsx
 * Full page: Nav, Hero, Demo (tabs), How It Works, Metrics, Limitations, Footer.
 *
 * Text corrections from the brief:
 *  - "12 FPS / stale frames dropped" removed — this described the old live worker.
 *    Offline engine samples at 6 poses per source second.
 *  - Meta description fixed (handled in index.html).
 */
import { useEffect, useRef, useState } from 'react';
import { ExamplePanel } from './components/ExamplePanel';
import { UploadPanel } from './components/UploadPanel';
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

type DemoTab = 'fall' | 'normal' | 'upload';

function DemoSection({ tab, onTabChange }: { tab: DemoTab; onTabChange: (tab: DemoTab) => void }) {

  return (
    <section className="demo" id="demo" aria-labelledby="demo-title">
      <div className="container">
        <div className="section-header">
          <h2 className="section-title" id="demo-title">Live Demo</h2>
          <p className="section-subtitle">Select an approved example or upload a short clip (MP4, max 50 MB, 60 s)</p>
        </div>

        <div className="tabs" id="demo-tabs" role="tablist" aria-label="Demo mode selector">
          <button
            className={`tab${tab === 'fall' ? ' tab--active' : ''}`}
            id="tab-fall" role="tab"
            aria-selected={tab === 'fall'}
            aria-controls="panel-fall"
            onClick={() => onTabChange('fall')}
          >
            <span className="tab__icon" aria-hidden="true">🎬</span>
            Fall Example
          </button>
          <button
            className={`tab${tab === 'normal' ? ' tab--active' : ''}`}
            id="tab-normal" role="tab"
            aria-selected={tab === 'normal'}
            aria-controls="panel-normal"
            onClick={() => onTabChange('normal')}
          >
            <span className="tab__icon" aria-hidden="true">🚶</span>
            Normal Activity
          </button>
          <button
            className={`tab${tab === 'upload' ? ' tab--active' : ''}`}
            id="tab-upload" role="tab"
            aria-selected={tab === 'upload'}
            aria-controls="panel-upload"
            onClick={() => onTabChange('upload')}
          >
            <span className="tab__icon" aria-hidden="true">↑</span>
            Upload Video
          </button>
        </div>

        <div
          className={`demo-panel${tab === 'fall' ? '' : ' demo-panel--hidden'}`}
          id="panel-fall"
          role="tabpanel"
          aria-labelledby="tab-fall"
        >
          {tab === 'fall' && <ExamplePanel initialOutcome="fall" />}
        </div>

        <div
          className={`demo-panel${tab === 'normal' ? '' : ' demo-panel--hidden'}`}
          id="panel-normal"
          role="tabpanel"
          aria-labelledby="tab-normal"
        >
          {tab === 'normal' && <ExamplePanel initialOutcome="no_fall" />}
        </div>

        <div
          className={`demo-panel${tab === 'upload' ? '' : ' demo-panel--hidden'}`}
          id="panel-upload"
          role="tabpanel"
          aria-labelledby="tab-upload"
        >
          {tab === 'upload' && <UploadPanel />}
        </div>
      </div>
    </section>
  );
}

// ─── How It Works ────────────────────────────────────────────────────────────
// Fixed: removed "12 FPS / stale frames" — describes old live worker, not offline engine.
// Offline engine: 6 poses per source second, reproducible by timestamp.

function HowItWorks() {
  return (
    <section className="pipeline-section" id="how-it-works" aria-labelledby="pipeline-title">
      <div className="container">
        <div className="section-header">
          <h2 className="section-title" id="pipeline-title">How It Works</h2>
          <p className="section-subtitle">A five-stage offline pipeline from raw video to fall probability</p>
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
            {/* Fixed: old live worker described "12 FPS, stale frames dropped". Offline engine uses timestamp-based sampling. */}
            <p className="pipeline-step__desc">
              Frames are sampled at ~6 poses per source second, selected by video timestamp for reproducibility.
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
            <h3 className="pipeline-step__title">Person Detection</h3>
            <p className="pipeline-step__desc">YOLOX-tiny finds the largest person on every sampled frame in the offline engine.</p>
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
            <h3 className="pipeline-step__title">Pose Estimation</h3>
            <p className="pipeline-step__desc">RTMPose-s estimates 17 COCO body keypoints per frame with per-joint confidence scores.</p>
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
// Numbers from docs/interfaces/metrics.md and approved by Person 4.
// precision 97.09%, recall 94.75%, F1 95.90% — group-aware classifier test.

function Metrics() {
  return (
    <section className="metrics-section" id="metrics" aria-labelledby="metrics-title">
      <div className="container">
        <div className="section-header">
          <h2 className="section-title" id="metrics-title">Performance Metrics</h2>
          <p className="section-subtitle">
            Held-out test set · Group-aware split · <strong>Not subject-independent</strong> · Threshold P(Fall) ≥ 0.50
          </p>
        </div>
        <div className="metrics-cards" role="list" aria-label="Model performance metrics">
          {[
            { value: '95.90%', label: 'Fall F1 Score', desc: 'Harmonic mean of precision and recall' },
            { value: '97.09%', label: 'Fall Precision', desc: 'TP=433, FP=13 on held-out test set' },
            { value: '94.75%', label: 'Fall Recall', desc: 'FN=24, TP=433 on held-out test set' },
            { value: '96.20%', label: 'Balanced Accuracy', desc: 'Equal weight per class' },
            { value: '99.61%', label: 'Avg Precision (PR-AUC)', desc: 'Area under precision-recall curve' },
            { value: '6,766', label: 'Dataset Samples', desc: 'Train, validation and test after deduplication' },
          ].map(m => (
            <div className="metric-card" role="listitem" key={m.label}>
              <div className="metric-card__glow" aria-hidden="true" />
              <div className="metric-card__value">{m.value}</div>
              <div className="metric-card__label">{m.label}</div>
              <div className="metric-card__desc">{m.desc}</div>
            </div>
          ))}
        </div>
        <div className="metrics-table-wrapper" role="region" aria-label="Confusion matrix">
          <h3 className="metrics-table-title">Confusion Matrix — Test Set</h3>
          <div className="table-scroll">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th scope="col" />
                  <th scope="col">Predicted: No Fall</th>
                  <th scope="col">Predicted: Fall</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Actual: No Fall</th>
                  <td className="cell-tn">TN = 541</td>
                  <td className="cell-fp">FP = 13</td>
                </tr>
                <tr>
                  <th scope="row">Actual: Fall</th>
                  <td className="cell-fn">FN = 24</td>
                  <td className="cell-tp">TP = 433</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Limitations ─────────────────────────────────────────────────────────────

function Limitations() {
  const items = [
    { icon: '👤', title: 'Single Person Only', body: 'Tracks only the largest detected person. Multi-person identity tracking is not implemented.' },
    { icon: '📊', title: 'Group-Aware, Not Subject-Independent', body: 'Prevents groups from crossing folds. Subject IDs unavailable — results may not generalise to unseen individuals.' },
    { icon: '⚡', title: 'CPU Throughput Gap', body: 'Pose inference runs slower than camera FPS on CPU. Measured FPS, RAM, and latency are pending live-service testing.' },
    { icon: '🔬', title: 'Train/Deploy Domain Gap', body: 'RTMPose at deployment may differ from the pose generator used during training. Gap not yet quantified.' },
    { icon: '🚫', title: 'Not a Medical Device', body: 'ICare is a research prototype. Must not be used as an emergency response or clinical monitoring system.' },
    { icon: '📋', title: 'Urgency Not Yet Adaptive', body: 'Motion urgency and reliability are instrumented but do not control model scheduling. Thresholds await validation traces.' },
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

function Footer({ onTabNav }: { onTabNav: (t: DemoTab) => void }) {
  return (
    <footer className="footer" role="contentinfo">
      <div className="container">
        <div className="footer__inner">
          <div className="footer__brand">
            <a href="#" className="nav__logo footer__logo" aria-label="ICare Home">
              <svg className="nav__logo-icon" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                <circle cx="16" cy="16" r="14" stroke="#ffa116" strokeWidth="2" />
                <path d="M10 16 L14 20 L22 12" stroke="#ffa116" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              <span className="nav__logo-text">ICare</span>
            </a>
            <p className="footer__tagline">Pose-Based Fall Detection · Research Prototype</p>
            <p className="footer__disclaimer">Not a medical device. Not a production monitoring system.</p>
          </div>
          <div className="footer__links">
            <div className="footer__col">
              <h4 className="footer__col-title">Demo</h4>
              <button className="footer__link" onClick={() => onTabNav('fall')}>Fall Example</button>
              <button className="footer__link" onClick={() => onTabNav('normal')}>Normal Activity</button>
              <button className="footer__link" onClick={() => onTabNav('upload')}>Upload Video</button>
            </div>
            <div className="footer__col">
              <h4 className="footer__col-title">Learn</h4>
              <a href="#how-it-works" className="footer__link">How It Works</a>
              <a href="#metrics" className="footer__link">Performance</a>
              <a href="#limitations" className="footer__link">Limitations</a>
            </div>
            <div className="footer__col">
              <h4 className="footer__col-title">Project</h4>
              <a href="https://github.com/vihaanbishnoi/ICare" className="footer__link" target="_blank" rel="noopener noreferrer">GitHub ↗</a>
            </div>
          </div>
        </div>
        <div className="footer__bottom">
          <p>ICare — Pose-Based Fall Detection Research · Group-aware baseline · Not subject-independent</p>
        </div>
      </div>
    </footer>
  );
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function Hero({ onNav }: { onNav: (tab: DemoTab) => void }) {
  return (
    <section className="hero" id="hero" aria-labelledby="hero-title">
      <HeroCanvas />
      <div className="hero__gradient" aria-hidden="true" />
      <div className="hero__content">
        <div className="hero__eyebrow" role="doc-subtitle">
          <span className="hero__dot" aria-hidden="true" />
          Research Prototype · Not a medical device
        </div>
        <h1 className="hero__title" id="hero-title">
          AI-Powered<br />
          <span className="hero__title-gradient">Fall Detection</span>
        </h1>
        <p className="hero__subtitle">
          Temporal pose analysis for offline video-based fall detection.<br />
          <span className="hero__stack">YOLOX · RTMPose · PoseC3D · ONNX Runtime</span>
        </p>
        <div className="hero__actions">
          <button className="btn btn--primary" id="hero-btn-fall" onClick={() => { document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); onNav('fall'); }}>
            <span className="btn__icon" aria-hidden="true">▶</span>
            Watch Fall Example
          </button>
          <button className="btn btn--secondary" id="hero-btn-normal" onClick={() => { document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); onNav('normal'); }}>
            <span className="btn__icon" aria-hidden="true">▶</span>
            Normal Activity
          </button>
          <button className="btn btn--outline" id="hero-btn-upload" onClick={() => { document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); onNav('upload'); }}>
            <span className="btn__icon" aria-hidden="true">↑</span>
            Upload Video
          </button>
        </div>
        <div className="hero__stats" aria-label="Key model performance metrics">
          {[
            { value: '95.90%', label: 'Fall F1' },
            { value: '97.09%', label: 'Precision' },
            { value: '94.75%', label: 'Recall' },
            { value: '99.61%', label: 'Avg Precision' },
          ].map((s, i, arr) => (
            <span key={s.label} style={{ display: 'contents' }}>
              <div className="hero__stat">
                <span className="hero__stat-value">{s.value}</span>
                <span className="hero__stat-label">{s.label}</span>
              </div>
              {i < arr.length - 1 && <div className="hero__stat-divider" aria-hidden="true" />}
            </span>
          ))}
        </div>
        <p className="hero__stats-disclaimer">Group-aware split · Not subject-independent · Research prototype</p>
      </div>
      <a href="#demo" className="hero__scroll" aria-label="Scroll to demo">
        <div className="hero__scroll-icon" aria-hidden="true">
          <div className="hero__scroll-arrow" />
        </div>
      </a>
    </section>
  );
}

// ─── Root App ────────────────────────────────────────────────────────────────

export default function App() {
  const [demoTab, setDemoTab] = useState<DemoTab>('fall');

  const goToDemo = (tab: DemoTab) => {
    setDemoTab(tab);
    setTimeout(() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }), 10);
  };

  return (
    <>
      <Nav />
      <main>
        <Hero onNav={setDemoTab} />
        <DemoSection tab={demoTab} onTabChange={setDemoTab} />
        <HowItWorks />
        <Metrics />
        <Limitations />
      </main>
      <Footer onTabNav={goToDemo} />
    </>
  );
}
