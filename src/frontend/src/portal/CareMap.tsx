/** Floor plan of the care home: rooms glow by today's falls, wings show a heat zone. */
import type { KeyboardEvent } from 'react';
import { DETECTOR, residentName, wingLabel, type FallEvent, type Resident } from './data';

interface Room { id: string; x: number; y: number; w: number; h: number; wing: string }

// Floor plan in SVG units (1000 × 480).
const ROOMS_LAYOUT: Room[] = [
  // West wing (left)
  { id: '201', x: 30, y: 40, w: 120, h: 110, wing: 'West' }, { id: '202', x: 160, y: 40, w: 120, h: 110, wing: 'West' },
  { id: '203', x: 30, y: 210, w: 120, h: 110, wing: 'West' }, { id: '204', x: 160, y: 210, w: 120, h: 110, wing: 'West' },
  // East wing (right)
  { id: '101', x: 720, y: 40, w: 120, h: 110, wing: 'East' }, { id: '102', x: 850, y: 40, w: 120, h: 110, wing: 'East' },
  { id: '103', x: 720, y: 210, w: 120, h: 110, wing: 'East' }, { id: '104', x: 850, y: 210, w: 120, h: 110, wing: 'East' },
  // Garden wing (bottom centre)
  { id: '301', x: 330, y: 360, w: 80, h: 90, wing: 'Garden' }, { id: '302', x: 420, y: 360, w: 80, h: 90, wing: 'Garden' },
  { id: '303', x: 510, y: 360, w: 80, h: 90, wing: 'Garden' }, { id: '304', x: 600, y: 360, w: 80, h: 90, wing: 'Garden' },
  // Camera / detector room (centre)
  { id: DETECTOR.room, x: 560, y: 40, w: 120, h: 80, wing: DETECTOR.wing },
];

const COMMON = [
  { label: 'Lounge & dining', x: 330, y: 40, w: 220, h: 150 },
  { label: 'Nurse station', x: 330, y: 200, w: 110, h: 110 },
  { label: 'Reception', x: 450, y: 200, w: 230, h: 110 },
  { label: 'CCTV room', x: 560, y: 130, w: 120, h: 60, note: true },
];

const ZONES: Record<string, { cx: number; cy: number; r: number }> = {
  West: { cx: 155, cy: 180, r: 200 }, East: { cx: 845, cy: 180, r: 200 },
  Garden: { cx: 505, cy: 405, r: 190 }, [DETECTOR.wing]: { cx: 620, cy: 80, r: 110 },
};

export function CareMap({ falls, residents, onRoom }: { falls: FallEvent[]; residents: Resident[]; onRoom: (room: string) => void }) {
  const byRoom = new Map<string, number>();
  const openRooms = new Set<string>();
  for (const f of falls) {
    byRoom.set(f.room, (byRoom.get(f.room) ?? 0) + 1);
    if (!f.acknowledgedAt) openRooms.add(f.room);
  }
  const maxRoom = Math.max(1, ...byRoom.values());
  const wings = ['East', 'West', 'Garden', DETECTOR.wing];
  const byWing = new Map(wings.map(w => [w, falls.filter(f => f.wing === w).length]));
  const maxWing = Math.max(1, ...byWing.values());
  const ranked = [...byWing].sort((a, b) => b[1] - a[1]);
  const who = (room: string) => residents.find(r => r.room === room);
  const key = (room: string) => (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRoom(room); } };

  return <div className="p-map">
    <svg className="p-map__svg" viewBox="0 0 1000 480" role="img" aria-label="Care home floor plan coloured by falls today">
      <defs>
        <radialGradient id="p-zone"><stop offset="0%" stopColor="#f26b1d" stopOpacity=".55" /><stop offset="100%" stopColor="#f26b1d" stopOpacity="0" /></radialGradient>
        <pattern id="p-grass" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M0 12L12 0" stroke="currentColor" strokeOpacity=".12" /></pattern>
      </defs>
      {/* building shell and corridors */}
      <rect className="p-map__shell" x="15" y="25" width="970" height="440" rx="22" />
      <rect className="p-map__corridor" x="30" y="160" width="250" height="40" rx="6" />
      <rect className="p-map__corridor" x="720" y="160" width="250" height="40" rx="6" />
      <rect className="p-map__corridor" x="330" y="320" width="350" height="30" rx="6" />
      <rect className="p-map__garden" x="30" y="340" width="280" height="110" rx="14" />
      <rect className="p-map__garden" x="700" y="340" width="270" height="110" rx="14" />
      <text className="p-map__muted" x="170" y="400" textAnchor="middle">Garden</text>
      <text className="p-map__muted" x="835" y="400" textAnchor="middle">Courtyard</text>

      {/* wing heat zones */}
      {wings.map(w => { const n = byWing.get(w) ?? 0; const z = ZONES[w];
        return n ? <circle key={w} cx={z.cx} cy={z.cy} r={z.r * (0.55 + 0.45 * n / maxWing)} fill="url(#p-zone)" opacity={0.35 + 0.65 * n / maxWing} className="p-map__zone" /> : null; })}

      {COMMON.map(c => <g key={c.label}>
        <rect className="p-map__common" x={c.x} y={c.y} width={c.w} height={c.h} rx="10" />
        <text className="p-map__muted" x={c.x + c.w / 2} y={c.y + c.h / 2 + 4} textAnchor="middle">{c.label}</text>
      </g>)}

      {ROOMS_LAYOUT.map(r => {
        const n = byRoom.get(r.id) ?? 0;
        const heat = n / maxRoom;
        const resident = who(r.id);
        const label = r.wing === DETECTOR.wing ? 'Camera feed' : resident ? residentName(residents, resident.id) : 'Vacant';
        return <g key={r.id} className="p-map__room" data-open={openRooms.has(r.id) ? 'true' : undefined} role="button" tabIndex={0}
          aria-label={`Room ${r.id}, ${label}, ${n} fall${n === 1 ? '' : 's'} today${openRooms.has(r.id) ? ', alert open' : ''}`}
          onClick={() => onRoom(r.id)} onKeyDown={key(r.id)}>
          <title>{`Room ${r.id} · ${label} · ${n} fall${n === 1 ? '' : 's'} today`}</title>
          <rect x={r.x} y={r.y} width={r.w} height={r.h} rx="10" style={{ ['--heat' as string]: heat }} className="p-map__roomrect" data-empty={n ? undefined : 'true'} />
          <text className="p-map__roomno" x={r.x + 12} y={r.y + 24}>{r.id}</text>
          <text className="p-map__roomname" x={r.x + 12} y={r.y + 42}>{label.split(' ')[0]}</text>
          {n > 0 && <g transform={`translate(${r.x + r.w - 18}, ${r.y + r.h - 18})`}>
            <circle r="13" className="p-map__count" /><text textAnchor="middle" y="4.5" className="p-map__countnum">{n}</text>
          </g>}
          {openRooms.has(r.id) && <circle cx={r.x + r.w - 14} cy={r.y + 14} r="6" className="p-map__ping" />}
        </g>;
      })}

      {/* wing labels */}
      <text className="p-map__wing" x="155" y="345" textAnchor="middle">WEST WING</text>
      <text className="p-map__wing" x="845" y="345" textAnchor="middle">EAST WING</text>
      <text className="p-map__wing" x="505" y="472" textAnchor="middle">GARDEN WING</text>
    </svg>

    <aside className="p-map__side">
      <p className="p-map__title">Fall zones by wing</p>
      <ol className="p-map__rank">
        {ranked.map(([w, n], i) => <li key={w} data-hot={i === 0 && n > 0 ? 'true' : undefined}>
          <span className="p-map__rankno">{i + 1}</span>
          <div><strong>{wingLabel(w)}</strong><i><b style={{ width: `${(n / maxWing) * 100}%` }} /></i></div>
          <span className="num">{n}</span>
        </li>)}
      </ol>
      <div className="p-map__legend">
        <span><i className="p-map__sw" data-l="0" />None</span><span><i className="p-map__sw" data-l="1" />Few</span>
        <span><i className="p-map__sw" data-l="2" />Most</span><span><i className="p-map__sw p-map__sw--open" />Alert open</span>
      </div>
    </aside>
  </div>;
}
