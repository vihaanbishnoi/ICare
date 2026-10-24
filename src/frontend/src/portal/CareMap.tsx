/** Floor plan of the care home: wings tinted by falls, rooms on a 4-step heat scale, room details on click. */
import { useState, type KeyboardEvent } from 'react';
import { ago, clock, DETECTOR, residentName, wingLabel, type FallEvent, type Resident } from './data';

interface Room { id: string; x: number; y: number; w: number; h: number; wing: string }
interface Zone { wing: string; label: string; x: number; y: number; w: number; h: number }

// Floor plan in SVG units (1000 × 500).
const ZONES: Zone[] = [
  { wing: 'West', label: 'West wing', x: 20, y: 20, w: 290, h: 320 },
  { wing: 'East', label: 'East wing', x: 690, y: 20, w: 290, h: 320 },
  { wing: 'Garden', label: 'Garden wing', x: 320, y: 340, w: 360, h: 150 },
];

const ROOMS_LAYOUT: Room[] = [
  { id: '201', x: 36, y: 64, w: 124, h: 118, wing: 'West' }, { id: '202', x: 170, y: 64, w: 124, h: 118, wing: 'West' },
  { id: '203', x: 36, y: 206, w: 124, h: 118, wing: 'West' }, { id: '204', x: 170, y: 206, w: 124, h: 118, wing: 'West' },
  { id: '101', x: 706, y: 64, w: 124, h: 118, wing: 'East' }, { id: '102', x: 840, y: 64, w: 124, h: 118, wing: 'East' },
  { id: '103', x: 706, y: 206, w: 124, h: 118, wing: 'East' }, { id: '104', x: 840, y: 206, w: 124, h: 118, wing: 'East' },
  { id: '301', x: 336, y: 384, w: 78, h: 92, wing: 'Garden' }, { id: '302', x: 424, y: 384, w: 78, h: 92, wing: 'Garden' },
  { id: '303', x: 512, y: 384, w: 78, h: 92, wing: 'Garden' }, { id: '304', x: 600, y: 384, w: 78, h: 92, wing: 'Garden' },
  { id: DETECTOR.room, x: 560, y: 20, w: 120, h: 150, wing: DETECTOR.wing },
];

const COMMON = [
  { label: 'Lounge & dining', x: 320, y: 20, w: 230, h: 150 },
  { label: 'Nurse station', x: 320, y: 180, w: 110, h: 150 },
  { label: 'Reception', x: 440, y: 180, w: 240, h: 150 },
];

const level = (n: number, max: number) => n === 0 ? 0 : n / max <= 0.34 ? 1 : n / max <= 0.67 ? 2 : 3;

export function CareMap({ falls, residents, onRoom }: { falls: FallEvent[]; residents: Resident[]; onRoom: (room: string) => void }) {
  const byRoom = new Map<string, FallEvent[]>();
  for (const f of falls) byRoom.set(f.room, [...(byRoom.get(f.room) ?? []), f]);
  const count = (room: string) => byRoom.get(room)?.length ?? 0;
  const isOpen = (room: string) => (byRoom.get(room) ?? []).some(f => !f.acknowledgedAt);
  const maxRoom = Math.max(1, ...[...byRoom.values()].map(v => v.length));
  const wings = ['East', 'West', 'Garden', DETECTOR.wing];
  const byWing = new Map(wings.map(w => [w, falls.filter(f => f.wing === w).length]));
  const maxWing = Math.max(1, ...byWing.values());
  const ranked = [...byWing].sort((a, b) => b[1] - a[1]);
  const hottest = [...byRoom].sort((a, b) => b[1].length - a[1].length)[0]?.[0] ?? ROOMS_LAYOUT[0].id;
  const [picked, setPicked] = useState<string | null>(null);
  const selected = picked ?? hottest;

  const who = (room: string) => residents.find(r => r.room === room);
  const label = (r: Room) => r.wing === DETECTOR.wing ? 'Camera feed' : who(r.id) ? residentName(residents, who(r.id)!.id) : 'Vacant';
  const key = (room: string) => (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPicked(room); } };

  const sel = ROOMS_LAYOUT.find(r => r.id === selected)!;
  const selFalls = (byRoom.get(selected) ?? []).slice().sort((a, b) => b.at - a.at);
  const openCount = selFalls.filter(f => !f.acknowledgedAt).length;

  return <div className="p-map">
    <svg className="p-map__svg" viewBox="0 0 1000 500" role="group" aria-label="Care home floor plan, rooms shaded by falls today">

      <defs>
        <pattern id="p-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><path d="M0 0V10" className="p-map__hatch" /></pattern>
      </defs>

      {/* outdoor areas */}
      <rect className="p-map__outdoor" x="20" y="350" width="290" height="140" rx="16" />
      <text className="p-map__muted" x="165" y="425" textAnchor="middle">Garden</text>
      <rect className="p-map__outdoor" x="690" y="350" width="290" height="140" rx="16" />
      <text className="p-map__muted" x="835" y="425" textAnchor="middle">Courtyard</text>

      {/* wing zones, tinted by share of falls */}
      {ZONES.map(z => { const n = byWing.get(z.wing) ?? 0;
        return <g key={z.wing}>
          <rect className="p-map__zone" x={z.x} y={z.y} width={z.w} height={z.h} rx="18" data-level={level(n, maxWing)} />
          <text className="p-map__wing" x={z.x + 16} y={z.y + 28}>{z.label.toUpperCase()}</text>
          <g transform={`translate(${z.x + z.w - 16}, ${z.y + 22})`}>
            <rect className="p-map__wingpill" x={-62} y={-13} width="62" height="22" rx="11" data-level={level(n, maxWing)} />
            <text className="p-map__wingpilltxt" x={-31} y={3} textAnchor="middle" data-level={level(n, maxWing)}>{n} {n === 1 ? 'fall' : 'falls'}</text>
          </g>
        </g>; })}

      {/* shared spaces */}
      {COMMON.map(c => <g key={c.label}>
        <rect className="p-map__common" x={c.x} y={c.y} width={c.w} height={c.h} rx="14" />
        <text className="p-map__muted" x={c.x + c.w / 2} y={c.y + c.h / 2 + 4} textAnchor="middle">{c.label}</text>
      </g>)}
      <g transform="translate(560, 330)" aria-hidden="true">
        <path d="M-16 0h32" className="p-map__door" /><text className="p-map__tiny" y="-8" textAnchor="middle">ENTRANCE</text>
      </g>

      {/* rooms */}
      {ROOMS_LAYOUT.map(r => {
        const n = count(r.id); const lv = level(n, maxRoom); const open = isOpen(r.id); const name = label(r);
        const small = r.w < 100;
        return <g key={r.id} className="p-map__room" role="button" tabIndex={0} aria-pressed={selected === r.id}
          aria-label={`Room ${r.id}, ${name}, ${n} fall${n === 1 ? '' : 's'} today${open ? ', alert open' : ''}`}
          data-level={lv} data-open={open ? 'true' : undefined} data-selected={selected === r.id ? 'true' : undefined}
          data-vacant={name === 'Vacant' ? 'true' : undefined}
          onClick={() => setPicked(r.id)} onKeyDown={key(r.id)}>
          <rect className="p-map__roomrect" x={r.x} y={r.y} width={r.w} height={r.h} rx="12" />
          <text className="p-map__roomno" x={r.x + 12} y={r.y + 26}>{r.wing === DETECTOR.wing ? 'CCTV' : r.id}</text>
          <text className="p-map__roomname" x={r.x + 12} y={r.y + 44}>{name.split(' ')[0]}</text>
          {n > 0 && <text className="p-map__roomfalls" x={r.x + 12} y={r.y + r.h - 14}>{n}{small ? '' : n === 1 ? ' fall' : ' falls'}</text>}
          {open && <g transform={`translate(${r.x + r.w - 14}, ${r.y + 16})`}>
            <circle r="10" className="p-map__pingring" /><circle r="5" className="p-map__ping" />
          </g>}
        </g>;
      })}
    </svg>

    <aside className="p-map__side">
      <section className="p-map__detail" aria-live="polite">
        <header>
          <span className="p-map__detailno" data-level={level(count(selected), maxRoom)}>{sel.wing === DETECTOR.wing ? 'CCTV' : selected}</span>
          <div><strong>{label(sel)}</strong><small>{wingLabel(sel.wing)}</small></div>
          {openCount > 0 && <span className="p-badge" data-tone="bad">{openCount} open</span>}
        </header>
        <div className="p-map__stats">
          <div><span>Falls today</span><strong className="num">{selFalls.length}</strong></div>
          <div><span>Last fall</span><strong className="num">{selFalls[0] ? clock(selFalls[0].at) : '–'}</strong></div>
        </div>
        {selFalls[0] && <p className="p-muted p-small">Most recent {ago(selFalls[0].at)}{selFalls[0].acknowledgedAt ? ', attended' : ', waiting for staff'}.</p>}
        {selFalls.length > 0
          ? <button type="button" className="p-btn p-btn--block" onClick={() => onRoom(selected)}>View room incidents</button>
          : <p className="p-muted p-small">No falls in this room today.</p>}
      </section>

      <section>
        <p className="p-map__title">Fall zones by wing</p>
        <ol className="p-map__rank">
          {ranked.map(([w, n], i) => <li key={w} data-hot={i === 0 && n > 0 ? 'true' : undefined}>
            <span className="p-map__rankno">{i + 1}</span>
            <div><strong>{wingLabel(w)}</strong><i><b style={{ width: `${(n / maxWing) * 100}%` }} /></i></div>
            <span className="num">{n}</span>
          </li>)}
        </ol>
      </section>

      <div className="p-map__legend" aria-label="Legend">
        {['None', 'Low', 'Medium', 'High'].map((l, i) => <span key={l}><i className="p-map__sw" data-level={i} />{l}</span>)}
        <span><i className="p-map__sw p-map__sw--open" />Alert open</span>
      </div>
    </aside>
  </div>;
}
