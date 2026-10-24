/** Small shared pieces for the care portal: icons, badges, the 5-second clip player and modal. */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { STATUS_LABEL, type ResidentStatus } from './data';

const paths: Record<string, string> = {
  grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  live: 'M12 12m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4M4.9 4.9a10 10 0 0 0 0 14.2M19.1 4.9a10 10 0 0 1 0 14.2',
  alert: 'M12 3l9.5 17h-19zM12 10v4.5M12 17.2v.3',
  report: 'M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h5',
  users: 'M9 11a3.5 3.5 0 1 0 0-7a3.5 3.5 0 0 0 0 7zM2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14.8c2 .6 3.2 2.3 3.5 5.2',
  camera: 'M3 7h4l2-2.5h6L17 7h4v12H3zM12 16.5a3.5 3.5 0 1 0 0-7a3.5 3.5 0 0 0 0 7z',
  bell: 'M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0',
  send: 'M21 3L10 14M21 3l-6.5 18-4.5-7-7-4.5z',
  download: 'M12 4v11M7 10.5l5 5 5-5M4 20h16',
  play: 'M8 5.5v13l11-6.5z',
  pause: 'M8 5h3v14H8zM13 5h3v14h-3z',
  logout: 'M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  close: 'M6 6l12 12M18 6L6 18',
  home: 'M4 11l8-7 8 7v9h-5v-6H9v6H4z',
  message: 'M4 5h16v11H9l-5 4z',
  clock: 'M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18zM12 7v5l3.5 2',
  sun: 'M12 16.5a4.5 4.5 0 1 0 0-9a4.5 4.5 0 0 0 0 9zM12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z',
  room: 'M5 21V4h11v17M16 7h3v14M9 13v1',
  heart: 'M12 20s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.4 4.3 4.3 0 0 1 19.5 10c0 5.4-7.5 10-7.5 10z',
  bolt: 'M13 3L5 13.5h6L10 21l8-10.5h-6z',
};

export function Icon({ name, size = 18 }: { name: keyof typeof paths | string; size?: number }) {
  return <svg className="p-icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function Logo() {
  return <div className="p-logo">
    <svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="10" />
      <path d="M10 17.5c0-3.6 2.7-6.5 6-6.5s6 2.9 6 6.5M16 11V7.5M12.5 21.5h7" /></svg>
    <div><strong>ICare</strong><span>Fall-safe living</span></div>
  </div>;
}

export function StatusPill({ status }: { status: ResidentStatus }) {
  return <span className="p-status" data-status={status}><span className="p-status__dot" />{STATUS_LABEL[status]}</span>;
}

export function Delta({ value, goodWhenDown = true }: { value: number; goodWhenDown?: boolean }) {
  const good = goodWhenDown ? value <= 0 : value >= 0;
  return <span className="p-delta" data-tone={good ? 'good' : 'bad'}>{value > 0 ? '+' : ''}{value}</span>;
}

export function Initials({ name, tone = 0 }: { name: string; tone?: number }) {
  const initials = name.split(' ').map(p => p[0]).slice(0, 2).join('');
  return <span className="p-avatar" data-tone={tone % 5}>{initials}</span>;
}

export function Modal({ title, onClose, children, wide }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} className="p-modal" data-wide={wide ? 'true' : undefined} onClose={onClose}
    onClick={e => { if (e.target === ref.current) ref.current?.close(); }}>
    <div className="p-modal__inner">
      <header className="p-modal__head"><h2>{title}</h2>
        <button type="button" className="p-iconbtn" aria-label="Close" onClick={() => ref.current?.close()}><Icon name="close" /></button>
      </header>
      {children}
    </div>
  </dialog>;
}

/**
 * Five-second incident clip. No recordings exist in this demo, so the clip is a
 * pose-only reconstruction (skeleton, no camera image) generated from the event seed.
 * A real deployment would stream the stored 5 s window around the detection here.
 */
export function ClipPlayer({ seed, room, at, label }: { seed: number; room: string; at: number; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(true);
  const LEN = 5;

  useEffect(() => {
    if (!playing) return;
    let raf = 0; let last = performance.now();
    const tick = (n: number) => {
      setT(prev => { const next = prev + (n - last) / 1000; return next >= LEN ? 0 : next; });
      last = n; raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  useEffect(() => {
    const c = canvas.current; const ctx = c?.getContext('2d'); if (!c || !ctx) return;
    const W = c.width, H = c.height;
    const dir = seed % 2 ? 1 : -1;
    ctx.fillStyle = '#16191d'; ctx.fillRect(0, 0, W, H);
    // floor and room outline
    ctx.strokeStyle = 'rgba(255,255,255,0.08)'; ctx.lineWidth = 1;
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, H * 0.72); ctx.lineTo(x + (x - W / 2) * 0.6, H); ctx.stroke(); }
    ctx.beginPath(); ctx.moveTo(0, H * 0.72); ctx.lineTo(W, H * 0.72); ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.05)'; ctx.fillRect(W * 0.08, H * 0.42, W * 0.22, H * 0.3); // bed
    // fall progress: stand → stumble (1.6-2.6 s) → on floor
    const p = Math.min(1, Math.max(0, (t - 1.6) / 1.0));
    const ease = p * p * (3 - 2 * p);
    const walk = Math.min(t, 1.6) * 30;
    const baseX = W * 0.5 + dir * (walk + ease * 30);
    const floor = H * 0.86;
    const angle = dir * ease * (Math.PI / 2.1);
    const s = H / 360;
    const pts: Record<string, [number, number]> = {
      head: [0, -150], neck: [0, -128], sh_l: [-18, -122], sh_r: [18, -122], el_l: [-26, -92], el_r: [26 + ease * 14, -95 + ease * 20],
      wr_l: [-28, -64], wr_r: [32 + ease * 22, -70 + ease * 30], hip: [0, -66], hip_l: [-11, -64], hip_r: [11, -64],
      kn_l: [-14 + Math.sin(t * 7) * 6 * (1 - ease), -32], kn_r: [14 - Math.sin(t * 7) * 6 * (1 - ease), -32], an_l: [-15, 0], an_r: [16, 0],
    };
    const tf = ([x, y]: [number, number]): [number, number] => {
      const cx = x * s, cy = y * s;
      return [baseX + cx * Math.cos(angle) - cy * Math.sin(angle), floor + cx * Math.sin(angle) + cy * Math.cos(angle) - ease * 6 * s];
    };
    const bones = [['neck', 'hip'], ['sh_l', 'sh_r'], ['sh_l', 'el_l'], ['el_l', 'wr_l'], ['sh_r', 'el_r'], ['el_r', 'wr_r'],
      ['hip_l', 'hip_r'], ['hip_l', 'kn_l'], ['kn_l', 'an_l'], ['hip_r', 'kn_r'], ['kn_r', 'an_r'], ['neck', 'head']];
    const alert = t > 2.3;
    ctx.lineCap = 'round'; ctx.lineWidth = 4 * s; ctx.strokeStyle = alert ? '#ff7a45' : '#d8f45b';
    for (const [a, b] of bones) { const A = tf(pts[a]), B = tf(pts[b]); ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke(); }
    ctx.fillStyle = ctx.strokeStyle;
    for (const k of Object.keys(pts)) { const [x, y] = tf(pts[k]); ctx.beginPath(); ctx.arc(x, y, (k === 'head' ? 9 : 3.2) * s, 0, Math.PI * 2); ctx.fill(); }
    // detection box
    if (alert) {
      ctx.strokeStyle = '#ff7a45'; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
      const xs = Object.values(pts).map(tf); const minX = Math.min(...xs.map(q => q[0])) - 14, maxX = Math.max(...xs.map(q => q[0])) + 14;
      const minY = Math.min(...xs.map(q => q[1])) - 14, maxY = Math.max(...xs.map(q => q[1])) + 10;
      ctx.strokeRect(minX, minY, maxX - minX, maxY - minY); ctx.setLineDash([]);
      ctx.fillStyle = '#ff7a45'; ctx.fillRect(minX, minY - 22, 92, 20);
      ctx.fillStyle = '#16191d'; ctx.font = `600 12px system-ui`; ctx.fillText('FALL DETECTED', minX + 6, minY - 8);
    }
    // overlay text
    ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = '500 12px ui-monospace, monospace';
    const stamp = new Date(at - 2500 + t * 1000);
    ctx.fillText(`ROOM ${room}  ·  ${stamp.toLocaleTimeString([], { hour12: false })}`, 14, 22);
    ctx.fillStyle = '#ff5a5a'; ctx.beginPath(); ctx.arc(W - 46, 18, 4, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.fillText('REC', W - 38, 22);
  }, [t, seed, room, at]);

  return <div className="p-clip">
    <canvas ref={canvas} width={720} height={405} aria-label={label} />
    <div className="p-clip__bar">
      <button type="button" className="p-clip__play" onClick={() => setPlaying(v => !v)} aria-label={playing ? 'Pause clip' : 'Play clip'}>
        <Icon name={playing ? 'pause' : 'play'} size={16} />
      </button>
      <input type="range" min={0} max={LEN} step={0.05} value={t} aria-label="Clip position"
        onChange={e => { setPlaying(false); setT(Number(e.target.value)); }} />
      <span className="num">{t.toFixed(1)} / {LEN.toFixed(1)} s</span>
    </div>
    <p className="p-clip__note">Demo clip: simulated pose replay of the 5 s around detection. Connect the camera recorder to show stored footage here.</p>
  </div>;
}
