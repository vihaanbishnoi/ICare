/** Day picker, the centred fall alert and the detector model card. */
import { useEffect, useRef, useState } from 'react';
import { Icon } from './ui';

export const dayChipLabels = (count: number) => Array.from({ length: count }, (_, i) => {
  const d = new Date(); d.setDate(d.getDate() - i);
  return {
    short: i === 0 ? 'Today' : i === 1 ? 'Yesterday' : d.toLocaleDateString([], { weekday: 'short' }),
    date: d.toLocaleDateString([], { day: 'numeric', month: 'short' }),
  };
});

/** Last seven days as selectable chips, each with its fall count. */
export function DayStrip({ value, onChange, counts }: { value: number; onChange: (offset: number) => void; counts: number[] }) {
  const labels = dayChipLabels(counts.length);
  return <div className="p-days" role="tablist" aria-label="Choose a day">
    {counts.map((n, i) => <button key={i} type="button" role="tab" aria-selected={value === i} className="p-day"
      data-on={value === i ? 'true' : undefined} onClick={() => onChange(i)}>
      <span>{labels[i].short}</span><strong>{labels[i].date}</strong>
      <small data-tone={n ? 'bad' : 'good'}>{n} {n === 1 ? 'fall' : 'falls'}</small>
    </button>)}
  </div>;
}

/** Seven-day bar trend; the selected day is highlighted. */
export function Trend({ counts, value, onChange }: { counts: number[]; value: number; onChange: (i: number) => void }) {
  const max = Math.max(1, ...counts);
  const labels = dayChipLabels(counts.length);
  return <div className="p-trend" role="img" aria-label="Falls per day, last seven days">
    {[...counts].map((n, i) => ({ n, i })).reverse().map(({ n, i }) =>
      <div key={i} data-on={value === i ? 'true' : undefined} onClick={() => onChange(i)}>
        <b className="num">{n}</b><i style={{ height: `${8 + (n / max) * 80}%` }} /><span>{i === 0 ? 'Today' : labels[i].date}</span>
      </div>)}
  </div>;
}

/** Full-screen centred fall alert so it cannot be missed. */
export function BigAlert({ kicker, place, detail, time, extra, primary, onPrimary, secondary, onSecondary, onDismiss, more }: {
  kicker: string; place: string; detail: string; time: string; extra?: string; primary: string; onPrimary: () => void;
  secondary?: string; onSecondary?: () => void; onDismiss: () => void; more?: number;
}) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => { btn.current?.focus(); }, [place, time]);
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onDismiss(); };
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k);
  }, [onDismiss]);
  return <div className="p-bigalert" role="alertdialog" aria-modal="true" aria-labelledby="p-bigalert-title" aria-describedby="p-bigalert-desc">
    <div className="p-bigalert__card">
      <div className="p-bigalert__icon"><Icon name="alert" size={44} /></div>
      <p className="p-bigalert__kicker">{kicker}</p>
      <h2 id="p-bigalert-title">{place}</h2>
      <p id="p-bigalert-desc" className="p-bigalert__detail">{detail}</p>
      <div className="p-bigalert__meta"><span><Icon name="clock" size={16} />{time}</span>{extra && <span>{extra}</span>}</div>
      <div className="p-bigalert__actions">
        <button ref={btn} type="button" className="p-btn p-btn--lime p-btn--xl" onClick={onPrimary}>{primary}</button>
        {secondary && onSecondary && <button type="button" className="p-btn p-btn--ghost p-btn--xl" onClick={onSecondary}><Icon name="play" size={16} />{secondary}</button>}
      </div>
      <button type="button" className="p-link p-bigalert__dismiss" onClick={onDismiss}>
        Dismiss{more ? ` · ${more} more alert${more > 1 ? 's' : ''} waiting` : ''}
      </button>
    </div>
  </div>;
}

type ModelState = 'checking' | 'ready' | 'offline';

/** The project's two-stage detector, with live readiness from the local API. */
export function ModelCard() {
  const [state, setState] = useState<ModelState>('checking');
  const [version, setVersion] = useState<string | null>(null);
  useEffect(() => {
    let stop = false;
    const check = async () => {
      try {
        const res = await fetch('/api/v1/ready');
        const body = await res.json().catch(() => ({}));
        if (stop) return;
        setState(res.ok ? 'ready' : 'offline'); setVersion(res.ok ? body.model_version ?? null : null);
      } catch { if (!stop) setState('offline'); }
    };
    void check(); const id = window.setInterval(check, 10_000);
    return () => { stop = true; window.clearInterval(id); };
  }, []);
  return <section className="p-card p-model">
    <div className="p-stack">
      <div className="p-card__head"><span>Fall-detection model</span></div>
      <div className="p-model__flow">
        <div className="p-model__step"><strong>YOLO26n-pose</strong><small>17 COCO keypoints per person · 640×640</small></div>
        <span className="p-model__arrow" aria-hidden="true">→</span>
        <div className="p-model__step"><strong>PoseC3D SlowOnly-R50</strong><small>4 s pose window · classes: No Fall / Fall</small></div>
        <span className="p-model__arrow" aria-hidden="true">→</span>
        <div className="p-model__step"><strong>Incident</strong><small>opens at P(Fall) ≥ 0.50</small></div>
      </div>
      <p className="p-muted p-small">ONNX, runs on this computer's CPU. Use <b>Live detection</b> for a camera or <b>Analyze video</b> to upload a clip.</p>
    </div>
    <div className="p-model__state">
      {state === 'ready' && <span className="p-badge" data-tone="good">Model ready{version ? ` · ${version}` : ''}</span>}
      {state === 'checking' && <span className="p-badge" data-tone="info">Checking model…</span>}
      {state === 'offline' && <span className="p-badge" data-tone="bad">Model server offline</span>}
    </div>
    {state === 'offline' && <p className="p-error p-span-all">The model API isn't running. From the repository root run
      <code> python -m uvicorn icare.api.main:create_app --factory --host 127.0.0.1 --port 8000</code></p>}
  </section>;
}
