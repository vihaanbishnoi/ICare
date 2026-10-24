/** Care manager console: live room status, realtime fall alerts, clips, reports and family messaging. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ModeTabs, type Mode } from '../components/Chrome';
import { LivePanel } from '../components/LivePanel';
import { UploadPanel } from '../components/UploadPanel';
import {
  acknowledgeFall, ago, ALL_ROOMS, bytesLabel, clock, dayStats, DETECTOR, DETECTOR_ID, duration, residentName,
  responseSeconds, sendMessage, syncDetectorClips, useNow, useSimulation, useStore, wingLabel,
  type FallEvent, type Resident, type Session,
} from './data';
import { deleteRoomFall } from '../api/client';
import { useClipList } from '../hooks/useClips';
import type { ClipList } from '../types';
import { DangerZones } from './DangerZones';
import { downloadCsv, printReport } from './report';
import { FallClip, Icon, Initials, Logo, Modal, StatusPill } from './ui';
import { BigAlert, DayStrip, Trend } from './extras';
import { CareMap } from './CareMap';
import { ChatDock } from './ChatDock';
import { dayLabel, fallsForDay, HISTORY_DAYS } from './data';
import { useTheme } from '../lib/theme';
import { fetchDailyLogs, fetchDailySummary } from '../api/client';
import type { DailyLogEntry, DailySummaryResponse } from '../types';

type View = 'overview' | 'live' | 'incidents' | 'zones' | 'reports' | 'families' | 'detection';
const NAV: { id: View; label: string; icon: string }[] = [
  { id: 'overview', label: 'Overview', icon: 'grid' },
  { id: 'live', label: 'Live monitor', icon: 'live' },
  { id: 'incidents', label: 'Fall incidents', icon: 'alert' },
  { id: 'zones', label: 'Danger zones', icon: 'room' },
  { id: 'reports', label: 'Daily reports', icon: 'report' },
  { id: 'families', label: 'Family messages', icon: 'message' },
];

export function Manager({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const store = useStore();
  const [view, setView] = useState<View>('overview');
  const [clip, setClip] = useState<FallEvent | null>(null);
  const [attend, setAttend] = useState<FallEvent | null>(null);
  const [notify, setNotify] = useState<{ residentId: string | 'all'; preset?: string } | null>(null);
  const [toasts, setToasts] = useState<FallEvent[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  useSimulation(true);
  const nowT = useNow(1000);

  // Falls found by the real detector (live camera or uploaded video) join the feed with their clip.
  const { list: clipList, unavailable: clipsUnavailable } = useClipList(4000);
  useEffect(() => { if (clipList) syncDetectorClips(clipList.clips); }, [clipList]);

  const open = store.falls.filter(f => !f.acknowledgedAt);
  const resident = (id: string) => store.residents.find(r => r.id === id) ?? DETECTOR;

  // Realtime alerting: any fall not seen before raises a toast, a chime and a system notification.
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!seen.current) { seen.current = new Set(store.falls.map(f => f.id)); return; }
    const added = store.falls.filter(f => !seen.current!.has(f.id));
    added.forEach(f => seen.current!.add(f.id));
    // Clips already stored when the console opens are history, not new alerts.
    const fresh = added.filter(f => !f.clipId || Date.now() - f.at < 2 * 60_000);
    if (!fresh.length) return;
    setToasts(t => [...fresh, ...t].slice(0, 5));
    chime();
    for (const f of fresh) {
      try {
        if ('Notification' in window && Notification.permission === 'granted')
          new Notification(`Fall detected · Room ${f.room}`, { body: `${resident(f.residentId).name}, ${wingLabel(f.wing)}`, tag: f.id });
      } catch { /* notifications unavailable */ }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.falls]);

  useEffect(() => {
    try { if ('Notification' in window && Notification.permission === 'default') void Notification.requestPermission(); } catch { /* ignore */ }
  }, []);

  const dismissToast = (id: string) => setToasts(t => t.filter(x => x.id !== id));

  return <div className="p-app">
    <aside className="p-side">
      <div className="p-side__brand"><Logo /></div>
      <nav aria-label="Console">
        <p className="p-side__label">Main</p>
        {NAV.map(n => <button key={n.id} type="button" className="p-nav" aria-current={view === n.id ? 'page' : undefined} onClick={() => setView(n.id)}>
          <Icon name={n.icon} /><span>{n.label}</span>
          {n.id === 'incidents' && open.length > 0 && <span className="p-nav__count">{open.length}</span>}
        </button>)}
        <p className="p-side__label">Tools</p>
        <button type="button" className="p-nav" aria-current={view === 'detection' ? 'page' : undefined} onClick={() => setView('detection')}>
          <Icon name="cctv" /><span>CCTV</span>
        </button>
      </nav>
      <div className="p-side__foot">
        <div className="p-side__wings">
          <p className="p-side__label">Wings</p>
          {['East', 'West', 'Garden', DETECTOR.wing].map(w => {
            const n = w === DETECTOR.wing ? open.filter(f => f.residentId === DETECTOR_ID).length
              : store.residents.filter(r => r.wing === w && r.status === 'fall').length;
            return <div key={w} className="p-wing"><Icon name="room" /><span>{wingLabel(w)}</span>{n > 0 && <span className="p-nav__count">{n}</span>}</div>;
          })}
        </div>
        <div className="p-user">
          <Initials name={session.name} tone={2} />
          <div><strong>{session.name}</strong><small>Care manager</small></div>
          <button type="button" className="p-iconbtn" onClick={onSignOut} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button>
        </div>
      </div>
    </aside>

    <div className="p-main">
      <header className="p-top">
        <div className="p-top__hello">
          <Initials name={session.name} tone={2} />
          <div><h1>{greeting()}, {session.name.split(' ')[0]}</h1>
            <p>{open.length ? <><b className="p-red">{open.length} open fall alert{open.length > 1 ? 's' : ''}</b> need attention</> : 'All residents are safe right now'}</p></div>
        </div>
        <div className="p-top__actions">
          <span className="p-chip"><Icon name="clock" size={16} />Today, {new Date(nowT).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          <ThemeButton />
          <div className="p-bell">
            <button type="button" className="p-iconbtn p-iconbtn--ring" aria-label={`Alerts, ${open.length} open`} aria-expanded={bellOpen} onClick={() => setBellOpen(v => !v)}>
              <Icon name="bell" />{open.length > 0 && <span className="p-bell__dot">{open.length}</span>}
            </button>
            {bellOpen && <div className="p-pop" role="menu">
              <header><strong>Live alerts</strong><span className="p-muted">{open.length} open</span></header>
              {store.falls.slice(0, 6).map(f => <button type="button" key={f.id} className="p-pop__item" onClick={() => { setBellOpen(false); setClip(f); }}>
                <span className="p-pop__icon" data-open={!f.acknowledgedAt ? 'true' : undefined}><Icon name="alert" size={16} /></span>
                <span><strong>Fall · Room {f.room}</strong><small>{resident(f.residentId).name} · {ago(f.at, nowT)}</small></span>
              </button>)}
            </div>}
          </div>
          <button type="button" className="p-btn p-btn--primary" onClick={() => setNotify({ residentId: 'all' })}><Icon name="send" size={16} />Notify families</button>
        </div>
      </header>

      <main className="p-content">
        {view === 'overview' && <Overview falls={store.falls} residents={store.residents} now={nowT}
          onClip={setClip} onAttend={setAttend} onGo={setView} onNotify={id => setNotify({ residentId: id })} />}
        {view === 'live' && <LiveMonitor residents={store.residents} falls={store.falls} now={nowT} onClip={setClip} onAttend={setAttend} onNotify={id => setNotify({ residentId: id })} />}
        {view === 'incidents' && <Incidents falls={store.falls} residents={store.residents} now={nowT} onClip={setClip} onAttend={setAttend}
          clipInfo={clipList} clipsUnavailable={clipsUnavailable} />}
        {view === 'zones' && <DangerZones />}
        {view === 'reports' && <Reports falls={store.falls} residents={store.residents} />}
        {view === 'families' && <Families residents={store.residents} onNotify={id => setNotify({ residentId: id })} />}
        {view === 'detection' && <Detection />}
      </main>
    </div>

    <ChatDock residents={store.residents} from={session.name} />

    {toasts[0] && !clip && !attend && (() => { const f = toasts[0]; return <BigAlert kicker="Fall detected"
      place={`Room ${f.room}`} detail={`${resident(f.residentId).name} · ${wingLabel(f.wing)}`}
      time={`${clock(f.at)} · ${ago(f.at, nowT)}`} extra={`${Math.round(f.confidence * 100)}% confidence`}
      primary="Respond now" onPrimary={() => { dismissToast(f.id); setAttend(f); }}
      secondary="View clip" onSecondary={() => { dismissToast(f.id); setClip(f); }}
      onDismiss={() => dismissToast(f.id)} more={toasts.length - 1} />; })()}

    {clip && <Modal title={`Fall clip · Room ${clip.room}`} onClose={() => setClip(null)} wide>
      <FallClip fall={clip} label={`Simulated clip of the fall in room ${clip.room}`} />
      <div className="p-clipmeta">
        <div><span>Resident</span><strong>{resident(clip.residentId).name}</strong></div>
        <div><span>Detected</span><strong>{clock(clip.at)}</strong></div>
        <div><span>Confidence</span><strong>{Math.round(clip.confidence * 100)}%</strong></div>
        <div><span>Status</span><strong>{clip.acknowledgedAt ? `Attended in ${duration(responseSeconds(clip)!)}` : 'Open'}</strong></div>
      </div>
      <div className="p-modal__foot">
        {resident(clip.residentId).family && <button type="button" className="p-btn" onClick={() => { const f = clip; setClip(null); setNotify({ residentId: f.residentId, preset: 'fall' }); }}><Icon name="send" size={16} />Notify family</button>}
        {!clip.acknowledgedAt && <button type="button" className="p-btn p-btn--primary" onClick={() => { const f = clip; setClip(null); setAttend(f); }}><Icon name="check" size={16} />Mark attended</button>}
      </div>
    </Modal>}

    {attend && <AttendDialog fall={attend} resident={resident(attend.residentId)} by={session.name} onClose={() => setAttend(null)}
      onNotify={() => setNotify({ residentId: attend.residentId, preset: 'fall' })} />}
    {notify && <NotifyDialog residents={store.residents} initial={notify.residentId} preset={notify.preset} from={session.name} onClose={() => setNotify(null)} />}
  </div>;
}

function greeting() { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; }

function ThemeButton() {
  const { theme, toggle } = useTheme();
  return <button type="button" className="p-iconbtn p-iconbtn--ring" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
    <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
  </button>;
}

function chime() {
  try {
    const ctx = new AudioContext(); const o = ctx.createOscillator(); const g = ctx.createGain();
    o.type = 'sine'; o.frequency.setValueAtTime(880, ctx.currentTime); o.frequency.setValueAtTime(660, ctx.currentTime + 0.18);
    g.gain.setValueAtTime(0.0001, ctx.currentTime); g.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    o.connect(g).connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.5);
  } catch { /* audio blocked until the page is interacted with */ }
}

/* ---------------- Overview ---------------- */

function Overview({ falls, residents, now, onClip, onAttend, onGo, onNotify }: {
  falls: FallEvent[]; residents: Resident[]; now: number; onClip: (f: FallEvent) => void; onAttend: (f: FallEvent) => void;
  onGo: (v: View) => void; onNotify: (id: string) => void;
}) {
  const s = dayStats(falls);
  const name = (id: string) => residentName(residents, id);
  const rooms = [...s.byRoom].sort((a, b) => b[1] - a[1]);
  const maxRoom = Math.max(1, ...rooms.map(r => r[1]));
  const hourNow = new Date(now).getHours();
  const hours = s.byHour.slice(0, hourNow + 1);
  const attendedPct = s.total ? Math.round(((s.total - s.open) / s.total) * 100) : 100;

  const [alertTab, setAlertTab] = useState<'open' | 'all'>('open');
  const alertList = (alertTab === 'open' ? falls.filter(f => !f.acknowledgedAt) : falls).slice(0, 12);

  return <div className="p-grid">
    <section className="p-card">
      <header className="p-card__head"><span>Falls today</span><button type="button" className="p-btn p-btn--sm" onClick={() => onGo('reports')}>Report</button></header>
      <div className="p-kpi"><strong className="num">{s.total}</strong><span className="p-badge" data-tone={s.open ? 'bad' : 'good'}>{s.open} open</span></div>
      <HourBars hours={hours} />
      <ul className="p-list">
        {['East', 'West', 'Garden', DETECTOR.wing].map(w => { const n = falls.filter(f => f.wing === w).length;
          return <li key={w}><span><Icon name="room" size={16} />{wingLabel(w)}</span><b className="num">{n}</b><span className="p-muted">{s.total ? Math.round(n / s.total * 100) : 0}%</span></li>; })}
      </ul>
    </section>

    <section className="p-card p-span-2 p-livealerts">
      <header className="p-card__head">
        <span><span className="p-live-dot p-live-dot--alert" />Live fall alerts</span>
        <div className="p-seg" role="tablist" aria-label="Alert filter">
          <button type="button" role="tab" aria-selected={alertTab === 'open'} className="p-seg__item" data-on={alertTab === 'open' ? 'true' : undefined} onClick={() => setAlertTab('open')}>Open · {s.open}</button>
          <button type="button" role="tab" aria-selected={alertTab === 'all'} className="p-seg__item" data-on={alertTab === 'all' ? 'true' : undefined} onClick={() => setAlertTab('all')}>All today · {s.total}</button>
        </div>
      </header>
      <ul className="p-alerts p-alerts--scroll">
        {alertList.map(f => { const pct = Math.round(f.confidence * 100); const det = f.residentId === DETECTOR_ID;
          return <li key={f.id} data-open={!f.acknowledgedAt ? 'true' : undefined}>
          <span className="p-alerts__room" aria-hidden={det ? 'true' : undefined}>
            {det ? <><Icon name="cctv" size={18} /><small>CCTV</small></> : <><small>Room</small><strong>{f.room}</strong></>}
          </span>
          <div className="p-alerts__who">
            <strong>{det ? 'CCTV camera' : name(f.residentId)}</strong>
            <small>{det ? 'Live detector' : wingLabel(f.wing)} · {clock(f.at)}</small>
          </div>
          <div className="p-alerts__meta">
            {f.acknowledgedAt
              ? <span className="p-badge" data-tone="good"><Icon name="check" size={12} />Attended in {duration(responseSeconds(f)!)}</span>
              : <span className="p-badge" data-tone="bad"><Icon name="clock" size={12} />Waiting {ago(f.at, now).replace(' ago', '')}</span>}
            <span className="p-alerts__conf" title="Model confidence"><i><b style={{ width: `${pct}%` }} /></i><span className="num">{pct}%</span></span>
          </div>
          <div className="p-alerts__actions">
            <button type="button" className="p-btn p-btn--sm" onClick={() => onClip(f)} aria-label={`Play 5 second clip, ${det ? 'CCTV' : `room ${f.room}`}`}><Icon name="play" size={14} />Clip</button>
            {!f.acknowledgedAt
              ? <button type="button" className="p-btn p-btn--primary p-btn--sm" onClick={() => onAttend(f)}>Respond</button>
              : !det && <button type="button" className="p-btn p-btn--sm" onClick={() => onNotify(f.residentId)}>Notify</button>}
          </div>
        </li>; })}
        {!alertList.length && <li className="p-empty p-empty--inline"><Icon name="check" />{alertTab === 'open' ? 'No open alerts. Everyone is safe.' : 'No falls today.'}</li>}
      </ul>
    </section>

    <section className="p-card p-span-2">
      <header className="p-card__head"><span>Falls by room</span><button type="button" className="p-btn p-btn--sm" onClick={() => onGo('reports')}>Report</button></header>
      <div className="p-kpi"><strong className="num">{s.byRoom.size}</strong><span className="p-muted">rooms with a fall</span></div>
      <ul className="p-rooms">
        {rooms.slice(0, 6).map(([room, n]) => <li key={room}><span>Room {room}</span><i><b style={{ width: `${(n / maxRoom) * 100}%` }} /></i><strong className="num">{n}</strong></li>)}
        {!rooms.length && <li className="p-muted">No falls yet today.</li>}
      </ul>
    </section>

    <section className="p-card">
      <header className="p-card__head"><span>Response time</span><button type="button" className="p-btn p-btn--sm" onClick={() => onGo('incidents')}>Details</button></header>
      <div className="p-kpi"><strong className="num">{s.avgResponse === null ? '–' : duration(s.avgResponse)}</strong><span className="p-badge" data-tone={(s.avgResponse ?? 0) <= 120 ? 'good' : 'bad'}>avg</span></div>
      <ul className="p-list p-list--plain">
        <li><span>Alerts attended</span><b className="num">{s.total - s.open}/{s.total}</b><span className="p-badge" data-tone={attendedPct === 100 ? 'good' : 'bad'}>{attendedPct}%</span></li>
        <li><span>Under 2 minutes</span><b className="num">{falls.filter(f => (responseSeconds(f) ?? 1e9) <= 120).length}</b><span /></li>
        <li><span>Repeat-fall residents</span><b className="num">{[...new Set(falls.map(f => f.residentId))].filter(id => id !== DETECTOR_ID && falls.filter(f => f.residentId === id).length > 1).length}</b><span /></li>
      </ul>
      <div className="p-meter" aria-label={`${attendedPct}% of alerts attended`}><i style={{ width: `${attendedPct}%` }} /></div>
    </section>

    <section className="p-card p-span-3">
      <header className="p-card__head"><span><Icon name="map" size={18} />Care home fall map · today</span><span className="p-muted p-small">Rooms glow by number of falls · click a room to see its incidents</span></header>
      <CareMap falls={falls} residents={residents} onRoom={() => onGo('incidents')} />
    </section>
  </div>;
}

function HourBars({ hours }: { hours: number[] }) {
  const max = Math.max(1, ...hours);
  return <div className="p-hours" role="img" aria-label="Falls per hour today">
    {Array.from({ length: 24 }, (_, h) => <i key={h} data-future={h >= hours.length ? 'true' : undefined}
      style={{ height: `${h < hours.length ? 6 + (hours[h] / max) * 94 : 6}%` }} title={`${String(h).padStart(2, '0')}:00 · ${hours[h] ?? 0} falls`} />)}
    <div className="p-hours__axis"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
  </div>;
}

/* ---------------- Live monitor ---------------- */

function LiveMonitor({ residents, falls, now, onClip, onAttend, onNotify }: {
  residents: Resident[]; falls: FallEvent[]; now: number; onClip: (f: FallEvent) => void; onAttend: (f: FallEvent) => void; onNotify: (id: string) => void;
}) {
  const [wing, setWing] = useState('All');
  // The detector is one more monitored room: it alerts when the live camera or an upload finds a fall.
  const detectorFalls = falls.filter(f => f.residentId === DETECTOR_ID);
  const detectorLast = detectorFalls[0];
  const detector: Resident = { ...DETECTOR, status: detectorFalls.some(f => !f.acknowledgedAt) ? 'fall' : 'active', since: detectorLast?.at ?? now };
  const rooms = [...residents, detector];
  const list = rooms.filter(r => wing === 'All' || r.wing === wing).sort((a, b) => Number(b.status === 'fall') - Number(a.status === 'fall'));
  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Live monitor</h2><p className="p-muted"><span className="p-live-dot" />Updating in real time · {rooms.length} rooms</p></div>
      <div className="p-seg" role="tablist" aria-label="Wing">{['All', 'East', 'West', 'Garden', DETECTOR.wing].map(w =>
        <button key={w} type="button" role="tab" aria-selected={wing === w} className="p-seg__item" data-on={wing === w ? 'true' : undefined} onClick={() => setWing(w)}>{w}</button>)}</div>
    </div>
    <div className="p-rooms-grid">
      {list.map(r => { const latest = falls.find(f => f.residentId === r.id && !f.acknowledgedAt);
        const isDetector = r.id === DETECTOR_ID;
        return <article key={r.id} className="p-room" data-status={r.status}>
          <header><span className="p-room__no">Room {r.room}</span><StatusPill status={r.status} label={isDetector && r.status !== 'fall' ? 'Monitoring' : undefined} /></header>
          <div className="p-room__who"><Initials name={r.name} tone={Number(r.id.slice(1))} /><div><strong>{r.name}</strong>
            <small>{isDetector ? 'Live camera and uploaded videos' : `${r.age} yrs · ${wingLabel(r.wing)}`}</small></div></div>
          <p className="p-room__since">{isDetector
            ? (detectorLast ? `${r.status === 'fall' ? 'Fall detected' : 'Last fall'} ${ago(r.since, now)}` : 'Watching for falls')
            : `${r.status === 'fall' ? 'Fall detected' : 'Status updated'} ${ago(r.since, now)}`}</p>
          <footer>
            {latest ? <>
              <button type="button" className="p-btn p-btn--sm" onClick={() => onClip(latest)}><Icon name="play" size={14} />Clip</button>
              <button type="button" className="p-btn p-btn--primary p-btn--sm" onClick={() => onAttend(latest)}>Respond</button>
            </> : isDetector
              ? (detectorLast ? <button type="button" className="p-btn p-btn--sm" onClick={() => onClip(detectorLast)}><Icon name="play" size={14} />Last clip</button>
                : <small className="p-muted">No falls detected yet</small>)
              : <button type="button" className="p-btn p-btn--sm" onClick={() => onNotify(r.id)}><Icon name="send" size={14} />Update family</button>}
          </footer>
        </article>; })}
    </div>
  </div>;
}

/* ---------------- Incidents ---------------- */

function Incidents({ falls, residents, now, onClip, onAttend, clipInfo, clipsUnavailable }: {
  falls: FallEvent[]; residents: Resident[]; now: number; onClip: (f: FallEvent) => void; onAttend: (f: FallEvent) => void;
  clipInfo: ClipList | null; clipsUnavailable: boolean;
}) {
  const [filter, setFilter] = useState<'all' | 'open' | 'attended'>('all');
  const [room, setRoom] = useState('all');
  const list = falls.filter(f => (filter === 'all' || (filter === 'open') === !f.acknowledgedAt) && (room === 'all' || f.room === room));
  const name = (id: string) => residentName(residents, id);
  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Fall incidents</h2><p className="p-muted">{falls.length} today · {falls.filter(f => !f.acknowledgedAt).length} open</p>
        <p className="p-muted p-small">{clipInfo
          ? `Detector clips: ${bytesLabel(clipInfo.storage_used_bytes)} of ${bytesLabel(clipInfo.storage_cap_bytes)} used, deleted after ${Math.round(clipInfo.retention_seconds / 3600)} h.`
          : clipsUnavailable ? 'The detector API is not running, so real clips cannot be loaded.' : ''}</p></div>
      <div className="p-filters">
        <div className="p-seg">{(['all', 'open', 'attended'] as const).map(k => <button key={k} type="button" className="p-seg__item" data-on={filter === k ? 'true' : undefined} aria-pressed={filter === k} onClick={() => setFilter(k)}>{k[0].toUpperCase() + k.slice(1)}</button>)}</div>
        <label className="p-select"><span className="sr-only">Room</span>
          <select value={room} onChange={e => setRoom(e.target.value)}><option value="all">All rooms</option>{ALL_ROOMS.map(r => <option key={r} value={r}>Room {r}</option>)}</select></label>
        <button type="button" className="p-btn" onClick={() => downloadCsv(list, residents, 'incidents')}><Icon name="download" size={16} />Export</button>
      </div>
    </div>
    <section className="p-card p-card--flush">
      <table className="p-table">
        <thead><tr><th>Resident</th><th>Room</th><th>Time</th><th>Confidence</th><th>Status</th><th>Response</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{list.map(f => <tr key={f.id} data-open={!f.acknowledgedAt ? 'true' : undefined}>
          <td><span className="p-cell-who"><Initials name={name(f.residentId)} tone={Number(f.residentId.slice(1))} />{name(f.residentId)}</span></td>
          <td>{f.room} <span className="p-muted">· {f.wing}</span>{f.clipId && <span className="p-badge" data-tone="info" title="Found by the detector, with a recorded clip">Detected</span>}</td>
          <td className="num">{clock(f.at)} <span className="p-muted">· {ago(f.at, now)}</span></td>
          <td className="num">{Math.round(f.confidence * 100)}%</td>
          <td>{f.acknowledgedAt ? <span className="p-badge" data-tone="good">Attended</span> : <span className="p-badge" data-tone="bad">Open</span>}</td>
          <td className="num">{f.acknowledgedAt ? duration(responseSeconds(f)!) : '–'}</td>
          <td className="p-table__act">
            <button type="button" className="p-btn p-btn--sm" onClick={() => onClip(f)}><Icon name="play" size={14} />Clip</button>
            {!f.acknowledgedAt && <button type="button" className="p-btn p-btn--primary p-btn--sm" onClick={() => onAttend(f)}>Respond</button>}
          </td>
        </tr>)}
        {!list.length && <tr><td colSpan={7} className="p-empty">No incidents match these filters.</td></tr>}</tbody>
      </table>
    </section>
  </div>;
}

/* ---------------- Reports ---------------- */

function Reports({ falls: todayFalls, residents }: { falls: FallEvent[]; residents: Resident[] }) {
  const [day, setDay] = useState(0);
  const counts = Array.from({ length: HISTORY_DAYS }, (_, i) => fallsForDay(i, todayFalls).length);
  const falls = fallsForDay(day, todayFalls);
  const s = dayStats(falls);
  const rooms = [...s.byRoom].sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rooms.map(r => r[1]));
  const name = (id: string) => residentName(residents, id);
  const byResident = useMemo(() => {
    const m = new Map<string, number>(); falls.forEach(f => m.set(f.residentId, (m.get(f.residentId) ?? 0) + 1));
    return [...m].sort((a, b) => b[1] - a[1]);
  }, [falls]);
  const peak = s.byHour.indexOf(Math.max(...s.byHour));
  const date = new Date(Date.now() - day * 86_400_000);
  const title = `Daily fall report · ${date.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })}`;

  const [summarising, setSummarising] = useState(false);
  const [summary, setSummary] = useState<DailySummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [showLogs, setShowLogs] = useState(false);
  const [dummyLogs, setDummyLogs] = useState<DailyLogEntry[]>([]);
  const [copied, setCopied] = useState(false);

  async function handleSummarise() {
    setSummarising(true);
    setSummaryError(null);
    try {
      const data = await fetchDailySummary('llama3.2:1b');
      setSummary(data);
      try {
        const logsRes = await fetchDailyLogs();
        setDummyLogs(logsRes.logs);
      } catch { /* preview is optional */ }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setSummaryError(msg);
    } finally {
      setSummarising(false);
    }
  }

  function copySummary() {
    if (!summary) return;
    let text = summary.summary;
    if (summary.structured_summary) {
      const s = summary.structured_summary;
      text = `Daily Fall Monitoring Report (${summary.model})\n\n` +
        `Executive Summary:\n${s.executive_summary}\n\n` +
        `Stats:\n- Total Events: ${s.incident_stats.total_events}\n- Confirmed Falls: ${s.incident_stats.confirmed_falls}\n- Near Falls: ${s.incident_stats.near_falls}\n- Avg Response: ${s.incident_stats.avg_response_time_seconds}s\n\n` +
        `High-Risk Residents:\n` + s.high_risk_residents.map(r => `- ${r.resident_name} (Room ${r.room}, ${r.wing}) [${r.risk_level}]: ${r.incident_summary} -> ${r.action_plan}`).join('\n') +
        `\n\nShift Recommendations:\n` + s.shift_handoff_recommendations.map(r => `- ${r}`).join('\n') +
        `\n\nShift Handoff Notes:\n${s.shift_handoff_notes}`;
    }
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Daily report · {dayLabel(day)}</h2><p className="p-muted">{date.toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}{day === 0 ? ' · updates live until midnight' : ' · closed day'}</p></div>
      <div className="p-filters">
        <button
          type="button"
          className="p-btn p-btn--ai"
          onClick={handleSummarise}
          disabled={summarising}
          title="Summarise daily dummy monitoring logs with Ollama llama3.2:1b"
        >
          <Icon name="sparkle" size={16} />
          {summarising ? 'Summarising...' : 'Summarise'}
        </button>
        <button type="button" className="p-btn" onClick={() => downloadCsv(falls, residents)}><Icon name="download" size={16} />CSV</button>
        <button type="button" className="p-btn p-btn--primary" onClick={() => printReport(falls, residents, title)}><Icon name="report" size={16} />Download PDF</button>
      </div>
    </div>

    {summarising && <section className="p-card p-card--ai-loading">
      <div className="p-ai-loading">
        <span className="p-ai-spinner" />
        <div>
          <strong>Summarising daily monitoring logs with Ollama (llama3.2:1b)...</strong>
          <p className="p-muted p-small">Analyzing incident patterns, response latencies, and care recommendations.</p>
        </div>
      </div>
    </section>}

    {summaryError && <section className="p-card p-inline-alert" role="alert">
      <Icon name="alert" size={18} />
      <div style={{ flex: 1 }}>
        <strong>Could not generate summary</strong>: {summaryError}
      </div>
      <button type="button" className="p-btn p-btn--sm" onClick={handleSummarise}>Retry</button>
    </section>}

    {summary && <section className="p-card p-card--ai-summary" aria-label="AI Daily Summary Report">
      <header className="p-card__head">
        <div className="p-ai-badge">
          <Icon name="sparkle" size={16} />
          <span><strong>AI Daily Summary</strong> · {summary.model} {summary.ollama_connected ? '· Ollama' : '· Analyzed'}</span>
          <span className="p-muted p-small">({summary.log_count} log entries analyzed)</span>
        </div>
        <div className="p-ai-actions">
          <button type="button" className="p-btn p-btn--sm" onClick={() => setShowLogs(!showLogs)}>
            <Icon name="report" size={14} />{showLogs ? 'Hide dummy logs' : 'View source logs'}
          </button>
          <button type="button" className="p-btn p-btn--sm" onClick={copySummary}>
            <Icon name={copied ? 'check' : 'download'} size={14} />{copied ? 'Copied' : 'Copy text'}
          </button>
          <button type="button" className="p-iconbtn" onClick={() => setSummary(null)} aria-label="Dismiss summary">
            <Icon name="close" size={14} />
          </button>
        </div>
      </header>

      {summary.notice && <div className="p-ai-notice"><Icon name="alert" size={14} /><span>{summary.notice}</span></div>}

      {summary.structured_summary ? <div className="p-summary-structured">
        <div className="p-exec-summary-box">
          <strong>Executive Summary</strong>
          <p>{summary.structured_summary.executive_summary}</p>
        </div>

        <div className="p-summary-kpis">
          <div className="p-summary-kpi">
            <span>Events Logged</span>
            <strong>{summary.structured_summary.incident_stats.total_events}</strong>
          </div>
          <div className="p-summary-kpi" data-tone={summary.structured_summary.incident_stats.confirmed_falls > 0 ? 'bad' : 'info'}>
            <span>Confirmed Falls</span>
            <strong>{summary.structured_summary.incident_stats.confirmed_falls}</strong>
          </div>
          <div className="p-summary-kpi" data-tone={summary.structured_summary.incident_stats.near_falls > 0 ? 'warn' : 'info'}>
            <span>Near Falls / Slips</span>
            <strong>{summary.structured_summary.incident_stats.near_falls}</strong>
          </div>
          <div className="p-summary-kpi" data-tone="info">
            <span>Avg Response Time</span>
            <strong>{summary.structured_summary.incident_stats.avg_response_time_seconds}s</strong>
          </div>
        </div>

        {summary.structured_summary.high_risk_residents?.length > 0 && <div className="p-summary-block">
          <div className="p-summary-block__title"><Icon name="alert" size={15} />High-Risk Residents & Required Actions</div>
          <div className="p-risk-grid">
            {summary.structured_summary.high_risk_residents.map((r, idx) => (
              <div key={idx} className="p-risk-card">
                <div className="p-risk-card__header">
                  <span><strong>{r.resident_name}</strong> · Room {r.room} ({r.wing} Wing)</span>
                  <span className="p-badge" data-tone={r.risk_level?.toLowerCase().includes('high') ? 'bad' : r.risk_level?.toLowerCase().includes('med') ? 'warn' : 'good'}>{r.risk_level} Risk</span>
                </div>
                <div className="p-risk-card__desc">{r.incident_summary}</div>
                <div className="p-risk-card__action"><strong>Action Plan:</strong> {r.action_plan}</div>
              </div>
            ))}
          </div>
        </div>}

        <div className="p-grid p-grid--2">
          {summary.structured_summary.key_observations?.length > 0 && <div className="p-summary-block">
            <div className="p-summary-block__title"><Icon name="bolt" size={15} />Key Clinical Observations</div>
            <ul className="p-summary-bullets">
              {summary.structured_summary.key_observations.map((obs, idx) => <li key={idx}>{obs}</li>)}
            </ul>
          </div>}

          {summary.structured_summary.shift_handoff_recommendations?.length > 0 && <div className="p-summary-block">
            <div className="p-summary-block__title"><Icon name="check" size={15} />Shift Handoff Recommendations</div>
            <ul className="p-summary-bullets">
              {summary.structured_summary.shift_handoff_recommendations.map((rec, idx) => <li key={idx}>{rec}</li>)}
            </ul>
          </div>}
        </div>

        {summary.structured_summary.shift_handoff_notes && <div className="p-handoff-callout">
          <strong>Shift Handoff Priority Notes</strong>
          <p>{summary.structured_summary.shift_handoff_notes}</p>
        </div>}
      </div> : <div className="p-summary-body">
        {summary.summary.split('\n\n').map((paragraph, idx) => {
          const trimmed = paragraph.trim();
          if (trimmed.startsWith('### ') || trimmed.startsWith('## ') || (trimmed.startsWith('**') && trimmed.endsWith('**') && !trimmed.includes('\n'))) {
            return <h3 key={idx} className="p-summary-heading">{trimmed.replace(/^[#*]+\s*|\*\*$/g, '')}</h3>;
          }
          if (trimmed.startsWith('* ') || trimmed.startsWith('- ') || /^\d+\.\s/.test(trimmed)) {
            const items = trimmed.split('\n').filter(l => l.trim());
            return <ul key={idx} className="p-summary-list">
              {items.map((item, iIdx) => <li key={iIdx}>{item.replace(/^(\*|-|\d+\.)\s*/, '')}</li>)}
            </ul>;
          }
          return <p key={idx} className="p-summary-para">{trimmed}</p>;
        })}
      </div>}

      {showLogs && <div className="p-logs-preview">
        <div className="p-logs-header">
          <h4>Dummy daily logs ({dummyLogs.length} events from daily_logs.csv)</h4>
          <span className="p-muted p-small">Source dataset for Ollama llama3.2:1b</span>
        </div>
        <div className="p-table-wrap">
          <table className="p-table p-table--compact">
            <thead>
              <tr><th>Time</th><th>Resident</th><th>Room</th><th>Wing</th><th>Event</th><th>Confidence</th><th>Response</th><th>Notes</th></tr>
            </thead>
            <tbody>
              {dummyLogs.map(l => <tr key={l.log_id}>
                <td className="num">{l.timestamp.split(' ')[1] || l.timestamp}</td>
                <td><strong>{l.resident_name}</strong></td>
                <td>{l.room}</td>
                <td>{l.wing}</td>
                <td><span className="p-badge" data-tone={l.event_type.includes('Fall') ? 'bad' : 'info'}>{l.event_type}</span></td>
                <td className="num">{Math.round(l.confidence * 100)}%</td>
                <td className="num">{l.response_time_seconds ? `${l.response_time_seconds}s` : '–'}</td>
                <td className="p-cell-note">{l.staff_notes}</td>
              </tr>)}
              {!dummyLogs.length && <tr><td colSpan={8} className="p-muted">Loading logs...</td></tr>}
            </tbody>
          </table>
        </div>
      </div>}
    </section>}

    <DayStrip value={day} onChange={setDay} counts={counts} />
    <section className="p-card">
      <header className="p-card__head"><span>Falls per day · last 7 days</span><span className="p-muted p-small">Click a bar to open that day</span></header>
      <Trend counts={counts} value={day} onChange={setDay} />
    </section>
    <div className="p-kpis">
      {[['Total falls', String(s.total)], ['Open alerts', String(s.open)], ['Rooms affected', String(s.byRoom.size)],
        ['Avg response', s.avgResponse === null ? '–' : duration(s.avgResponse)], ['Peak hour', s.total ? `${String(peak).padStart(2, '0')}:00` : '–']].map(([l, v]) =>
        <div key={l} className="p-card p-kpi-card"><span>{l}</span><strong className="num">{v}</strong></div>)}
    </div>
    <div className="p-grid p-grid--2">
      <section className="p-card">
        <header className="p-card__head"><span>Falls by room</span></header>
        <ul className="p-rooms">{rooms.map(([room, n]) => <li key={room}><span>Room {room}</span><i><b style={{ width: `${(n / max) * 100}%` }} /></i><strong className="num">{n}</strong></li>)}
          {!rooms.length && <li className="p-muted">No falls recorded.</li>}</ul>
      </section>
      <section className="p-card">
        <header className="p-card__head"><span>Falls by hour</span></header>
        <HourBars hours={day === 0 ? s.byHour.slice(0, new Date().getHours() + 1) : s.byHour} />
      </section>
      <section className="p-card">
        <header className="p-card__head"><span>Residents with falls</span></header>
        <ul className="p-list p-list--plain">{byResident.filter(([id]) => id !== DETECTOR_ID).map(([id, n]) => <li key={id}><span className="p-cell-who"><Initials name={name(id)} tone={Number(id.slice(1))} />{name(id)}</span><b className="num">{n}</b>{n > 1 ? <span className="p-badge" data-tone="bad">Review care plan</span> : <span />}</li>)}</ul>
      </section>
      <section className="p-card">
        <header className="p-card__head"><span>Incident log</span></header>
        <ul className="p-log">{[...falls].sort((a, b) => a.at - b.at).map(f => <li key={f.id}><span className="num">{clock(f.at)}</span><span>Room {f.room} · {name(f.residentId)}</span>
          {f.acknowledgedAt ? <span className="p-badge" data-tone="good">{duration(responseSeconds(f)!)}</span> : <span className="p-badge" data-tone="bad">Open</span>}</li>)}</ul>
      </section>
    </div>
  </div>;
}

/* ---------------- Families ---------------- */

function Families({ residents, onNotify }: { residents: Resident[]; onNotify: (id: string) => void }) {
  const { messages } = useStore();
  return <div className="p-stack">
    <div className="p-pagehead"><div><h2>Family messages</h2><p className="p-muted">Updates appear instantly in each family's portal.</p></div>
      <button type="button" className="p-btn p-btn--primary" onClick={() => onNotify('all')}><Icon name="send" size={16} />New message</button></div>
    <div className="p-grid p-grid--2">
      <section className="p-card p-card--flush">
        <header className="p-card__head p-pad"><span>Families</span></header>
        <ul className="p-list p-list--rows">{residents.map(r => <li key={r.id}>
          <span className="p-cell-who"><Initials name={r.family} tone={Number(r.id.slice(1))} /><span><strong>{r.family}</strong><small className="p-muted">Family of {r.name} · Room {r.room}</small></span></span>
          <button type="button" className="p-btn p-btn--sm" onClick={() => onNotify(r.id)}><Icon name="send" size={14} />Message</button></li>)}</ul>
      </section>
      <section className="p-card p-card--flush">
        <header className="p-card__head p-pad"><span>Sent</span><span className="p-muted p-small">{messages.length}</span></header>
        <ul className="p-msgs">{messages.map(m => <li key={m.id}><span className="p-badge" data-tone={m.kind === 'alert' ? 'bad' : m.kind === 'visit' ? 'info' : 'good'}>{m.kind}</span>
          <div><strong>{m.title}</strong><p>{m.body}</p><small className="p-muted">To {m.residentId === 'all' ? 'all families' : residents.find(r => r.id === m.residentId)?.family} · {ago(m.at)}</small></div></li>)}</ul>
      </section>
    </div>
  </div>;
}

/* ---------------- Detection (existing model UI) ---------------- */

function Detection() {
  const [mode, setMode] = useState<Mode>('live');
  return <div className="p-stack p-detection">
    <div className="p-pagehead"><div><h2>CCTV</h2><p className="p-muted">Watch a live camera with fall detection, or upload a recorded clip to analyze.</p></div>
      <ModeTabs mode={mode} onChange={setMode} prefix="portal" label="Detection mode" /></div>
    <section role="tabpanel" id="portal-panel-live" aria-labelledby="portal-tab-live" hidden={mode !== 'live'}>{mode === 'live' && <LivePanel />}</section>
    <section role="tabpanel" id="portal-panel-video" aria-labelledby="portal-tab-video" hidden={mode !== 'video'}><UploadPanel /></section>
  </div>;
}

/* ---------------- Dialogs ---------------- */

function AttendDialog({ fall, resident, by, onClose, onNotify }: { fall: FallEvent; resident: Resident; by: string; onClose: () => void; onNotify: () => void }) {
  const [note, setNote] = useState('');
  const [tell, setTell] = useState(true);
  const outcomes = ['No injury, helped up', 'Minor injury, first aid given', 'Nurse assessment requested', 'Ambulance called', 'False alarm'];
  return <Modal title={`Respond · Room ${fall.room}`} onClose={onClose}>
    <div className="p-attend">
      <div className="p-attend__who"><Initials name={resident.name} tone={Number(resident.id.slice(1))} /><div><strong>{resident.name}</strong><small className="p-muted">Detected {clock(fall.at)} · {ago(fall.at)}</small></div></div>
      <fieldset className="p-chips"><legend>Outcome</legend>
        {outcomes.map(o => <label key={o} className="p-chipopt"><input type="radio" name="outcome" checked={note === o} onChange={() => setNote(o)} /><span>{o}</span></label>)}
      </fieldset>
      <label className="p-field"><span>Note (optional)</span><input value={note} onChange={e => setNote(e.target.value)} placeholder="What happened?" /></label>
      {resident.family && <label className="p-check"><input type="checkbox" checked={tell} onChange={e => setTell(e.target.checked)} /><span>Notify {resident.family} after saving</span></label>}
    </div>
    <div className="p-modal__foot">
      <button type="button" className="p-btn" onClick={onClose}>Cancel</button>
      <button type="button" className="p-btn p-btn--primary" onClick={() => {
        acknowledgeFall(fall.id, by, note); onClose();
        // A false alarm must not count towards the room's danger zone.
        if (fall.clipId && note === 'False alarm') void deleteRoomFall(fall.room, fall.clipId).catch(() => undefined);
        if (tell && resident.family) onNotify();
      }}><Icon name="check" size={16} />Mark attended</button>
    </div>
  </Modal>;
}

const TEMPLATES = {
  update: { title: 'Daily update', body: 'Your parent is doing well today and is comfortable.' },
  fall: { title: 'A fall was detected', body: 'Our staff responded right away. Your parent is being looked after and we will call you with details.' },
  visit: { title: 'Visiting reminder', body: 'A reminder that visiting hours are 10:00–18:00 daily.' },
};

function NotifyDialog({ residents, initial, preset, from, onClose }: { residents: Resident[]; initial: string; preset?: string; from: string; onClose: () => void }) {
  const [to, setTo] = useState(initial);
  const [kind, setKind] = useState<keyof typeof TEMPLATES>(preset === 'fall' ? 'fall' : 'update');
  const [title, setTitle] = useState(TEMPLATES[kind].title);
  const [body, setBody] = useState(TEMPLATES[kind].body);
  const [sent, setSent] = useState(false);
  const pick = (k: keyof typeof TEMPLATES) => { setKind(k); setTitle(TEMPLATES[k].title); setBody(TEMPLATES[k].body); };
  const target = to === 'all' ? 'all families' : residents.find(r => r.id === to)?.family;
  return <Modal title="Notify families" onClose={onClose}>
    {sent ? <div className="p-sent"><span><Icon name="check" size={28} /></span><h3>Sent to {target}</h3><p className="p-muted">It is now visible in their family portal.</p>
      <div className="p-modal__foot"><button type="button" className="p-btn p-btn--primary" onClick={onClose}>Done</button></div></div>
    : <form onSubmit={e => { e.preventDefault(); sendMessage({ residentId: to, title, body, from, kind: kind === 'fall' ? 'alert' : kind }); setSent(true); }}>
      <label className="p-field"><span>To</span>
        <select value={to} onChange={e => setTo(e.target.value)}><option value="all">All families ({residents.length})</option>
          {residents.map(r => <option key={r.id} value={r.id}>{r.family} · family of {r.name}</option>)}</select></label>
      <div className="p-seg p-seg--full" role="radiogroup" aria-label="Message type">{(['update', 'fall', 'visit'] as const).map(k =>
        <button key={k} type="button" role="radio" aria-checked={kind === k} className="p-seg__item" data-on={kind === k ? 'true' : undefined} onClick={() => pick(k)}>{k === 'fall' ? 'Fall notice' : k === 'visit' ? 'Visit' : 'Update'}</button>)}</div>
      <label className="p-field"><span>Title</span><input required value={title} onChange={e => setTitle(e.target.value)} /></label>
      <label className="p-field"><span>Message</span><textarea required rows={4} value={body} onChange={e => setBody(e.target.value)} /></label>
      <div className="p-modal__foot"><button type="button" className="p-btn" onClick={onClose}>Cancel</button>
        <button type="submit" className="p-btn p-btn--primary"><Icon name="send" size={16} />Send to {to === 'all' ? 'everyone' : target?.split(' ')[0]}</button></div>
    </form>}
  </Modal>;
}
