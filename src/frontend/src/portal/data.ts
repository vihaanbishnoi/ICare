/**
 * Care portal demo data layer.
 *
 * There is no resident/room/account backend yet, so this module simulates a
 * facility feed in the browser. Fall events here are generated demo data, not
 * detector output. Messages and incidents are shared between tabs through
 * localStorage + BroadcastChannel so a manager tab and a family tab stay in sync.
 */
import { useEffect, useState, useSyncExternalStore } from 'react';

export type Role = 'family' | 'manager';
export type ResidentStatus = 'active' | 'resting' | 'away' | 'fall';

export interface Resident {
  id: string; name: string; age: number; room: string; wing: string;
  status: ResidentStatus; since: number; family: string; familyEmail: string;
}

export interface FallEvent {
  id: string; residentId: string; room: string; wing: string; at: number;
  confidence: number; acknowledgedAt: number | null; acknowledgedBy: string | null;
  note: string | null; clipSeed: number;
}

export interface FamilyMessage {
  id: string; residentId: string | 'all'; title: string; body: string; at: number;
  from: string; kind: 'update' | 'alert' | 'visit'; read: boolean;
}

export interface Session { role: Role; name: string; email: string; residentId?: string }

const now = () => Date.now();
const MIN = 60_000;
const HOUR = 60 * MIN;

const RESIDENTS_SEED: Omit<Resident, 'status' | 'since'>[] = [
  { id: 'r1', name: 'Margaret Shah', age: 82, room: '101', wing: 'East', family: 'Priya Shah', familyEmail: 'priya@family.demo' },
  { id: 'r2', name: 'Harold Brooks', age: 79, room: '102', wing: 'East', family: 'Daniel Brooks', familyEmail: 'daniel@family.demo' },
  { id: 'r3', name: 'Kamala Iyer', age: 88, room: '104', wing: 'East', family: 'Arjun Iyer', familyEmail: 'arjun@family.demo' },
  { id: 'r4', name: 'Walter Kim', age: 84, room: '201', wing: 'West', family: 'Grace Kim', familyEmail: 'grace@family.demo' },
  { id: 'r5', name: 'Rosa Martinez', age: 76, room: '203', wing: 'West', family: 'Lucia Martinez', familyEmail: 'lucia@family.demo' },
  { id: 'r6', name: 'Eugene Patel', age: 90, room: '204', wing: 'West', family: 'Neha Patel', familyEmail: 'neha@family.demo' },
  { id: 'r7', name: 'Dorothy Clarke', age: 81, room: '301', wing: 'Garden', family: 'Simon Clarke', familyEmail: 'simon@family.demo' },
  { id: 'r8', name: 'Ravi Menon', age: 86, room: '302', wing: 'Garden', family: 'Anita Menon', familyEmail: 'anita@family.demo' },
];

export const ROOMS = RESIDENTS_SEED.map(r => r.room);

function rand(seed: number) {
  let s = seed % 2147483647; if (s <= 0) s += 2147483646;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function seedFalls(): FallEvent[] {
  // A plausible earlier day so the dashboard is not empty on first open.
  const r = rand(Math.floor(now() / (24 * HOUR)));
  const start = new Date(); start.setHours(0, 0, 0, 0);
  const elapsed = Math.max(now() - start.getTime(), 2 * HOUR);
  const weights = [3, 1, 4, 1, 1, 5, 1, 2]; // some rooms see more falls
  const pool = RESIDENTS_SEED.flatMap((res, i) => Array(weights[i]).fill(res));
  return Array.from({ length: 9 }, (_, i) => {
    const res = pool[Math.floor(r() * pool.length)];
    const at = start.getTime() + Math.floor(r() * (elapsed - 10 * MIN));
    const ack = r() > 0.12 ? at + Math.floor((40 + r() * 260) * 1000) : null;
    return { id: `f-seed-${i}`, residentId: res.id, room: res.room, wing: res.wing, at,
      confidence: 0.6 + r() * 0.38, acknowledgedAt: ack, acknowledgedBy: ack ? 'Nurse on duty' : null,
      note: ack ? 'Checked by staff' : null, clipSeed: Math.floor(r() * 1e6) };
  }).sort((a, b) => b.at - a.at);
}

function seedMessages(): FamilyMessage[] {
  return [
    { id: 'm-seed-1', residentId: 'all', title: 'Visiting hours this weekend', body: 'Garden wing visits move to 10:00–13:00 on Saturday for the music afternoon.', at: now() - 5 * HOUR, from: 'Care team', kind: 'visit', read: false },
    { id: 'm-seed-2', residentId: 'r1', title: 'Margaret had a good morning', body: 'She joined the stretching session and ate a full breakfast.', at: now() - 2 * HOUR, from: 'Care team', kind: 'update', read: false },
  ];
}

/* ---------- shared store ---------- */

interface State { residents: Resident[]; falls: FallEvent[]; messages: FamilyMessage[]; day: string }
const KEY = 'icare-portal-v1';
const SESSION_KEY = 'icare-portal-session';
const today = () => new Date().toDateString();

function initial(): State {
  const r = rand(7);
  const statuses: ResidentStatus[] = ['active', 'resting', 'active', 'away', 'resting', 'active', 'resting', 'active'];
  return {
    day: today(),
    residents: RESIDENTS_SEED.map((res, i) => ({ ...res, status: statuses[i], since: now() - Math.floor(r() * 50) * MIN })),
    falls: seedFalls(), messages: seedMessages(),
  };
}

function load(): State {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as State;
      if (parsed.day === today() && parsed.residents?.length) return parsed;
    }
  } catch { /* storage unavailable */ }
  return initial();
}

let state: State = load();
const listeners = new Set<() => void>();
let channel: BroadcastChannel | null = null;
try { channel = new BroadcastChannel('icare-portal'); } catch { channel = null; }
channel?.addEventListener('message', () => { state = load(); listeners.forEach(l => l()); });

function commit(next: State) {
  state = next;
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* keep in memory */ }
  channel?.postMessage('changed');
  listeners.forEach(l => l());
}

const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };
export const useStore = () => useSyncExternalStore(subscribe, () => state);

export const residentById = (id: string) => state.residents.find(r => r.id === id);

export function acknowledgeFall(id: string, by: string, note: string) {
  const at = now();
  commit({ ...state, falls: state.falls.map(f => f.id === id ? { ...f, acknowledgedAt: at, acknowledgedBy: by, note: note || 'Attended' } : f),
    residents: state.residents.map(r => {
      const fall = state.falls.find(f => f.id === id);
      return fall && r.id === fall.residentId && r.status === 'fall' ? { ...r, status: 'resting', since: at } : r;
    }) });
}

export function sendMessage(msg: Omit<FamilyMessage, 'id' | 'at' | 'read'>) {
  commit({ ...state, messages: [{ ...msg, id: `m-${now()}`, at: now(), read: false }, ...state.messages] });
}

export function markRead(residentId: string) {
  commit({ ...state, messages: state.messages.map(m => m.residentId === residentId || m.residentId === 'all' ? { ...m, read: true } : m) });
}

/** Demo only: creates a simulated fall so the realtime alert path can be shown. */
export function simulateFall(residentId?: string) {
  const pool = state.residents.filter(r => r.status !== 'fall');
  const res = residentId ? state.residents.find(r => r.id === residentId) : pool[Math.floor(Math.random() * pool.length)];
  if (!res) return;
  const at = now();
  const fall: FallEvent = { id: `f-${at}`, residentId: res.id, room: res.room, wing: res.wing, at,
    confidence: 0.62 + Math.random() * 0.35, acknowledgedAt: null, acknowledgedBy: null, note: null,
    clipSeed: Math.floor(Math.random() * 1e6) };
  commit({ ...state, falls: [fall, ...state.falls],
    residents: state.residents.map(r => r.id === res.id ? { ...r, status: 'fall', since: at } : r) });
}

/** Light background drift so statuses look live. Only one tab (the manager) drives it. */
export function useSimulation(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    const drift = window.setInterval(() => {
      const options: ResidentStatus[] = ['active', 'resting', 'away'];
      const movable = state.residents.filter(r => r.status !== 'fall');
      if (!movable.length) return;
      const pick = movable[Math.floor(Math.random() * movable.length)];
      const status = options[Math.floor(Math.random() * options.length)];
      commit({ ...state, residents: state.residents.map(r => r.id === pick.id ? { ...r, status, since: now() } : r) });
    }, 9000);
    const falls = window.setInterval(() => { if (Math.random() < 0.35) simulateFall(); }, 45_000);
    return () => { window.clearInterval(drift); window.clearInterval(falls); };
  }, [enabled]);
}

/* ---------- session ---------- */

export function loadSession(): Session | null {
  try { const raw = sessionStorage.getItem(SESSION_KEY); return raw ? JSON.parse(raw) as Session : null; } catch { return null; }
}
export function saveSession(s: Session | null) {
  try { if (s) sessionStorage.setItem(SESSION_KEY, JSON.stringify(s)); else sessionStorage.removeItem(SESSION_KEY); } catch { /* ignore */ }
}
export const DEMO_RESIDENTS = RESIDENTS_SEED;

/* ---------- helpers ---------- */

export function useNow(intervalMs = 1000) {
  const [t, setT] = useState(now);
  useEffect(() => { const id = window.setInterval(() => setT(now()), intervalMs); return () => window.clearInterval(id); }, [intervalMs]);
  return t;
}

export function ago(at: number, ref = now()) {
  const s = Math.max(0, Math.round((ref - at) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60); if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60); return `${h} h ${m % 60} min ago`;
}
export const clock = (at: number) => new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
export const responseSeconds = (f: FallEvent) => f.acknowledgedAt ? Math.round((f.acknowledgedAt - f.at) / 1000) : null;
export const duration = (s: number) => s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`;

export const STATUS_LABEL: Record<ResidentStatus, string> = { active: 'Active', resting: 'Resting', away: 'Out of room', fall: 'Fall alert' };

export function dayStats(falls: FallEvent[]) {
  const byRoom = new Map<string, number>();
  const byHour = Array(24).fill(0) as number[];
  for (const f of falls) {
    byRoom.set(f.room, (byRoom.get(f.room) ?? 0) + 1);
    byHour[new Date(f.at).getHours()]++;
  }
  const acked = falls.filter(f => f.acknowledgedAt);
  const avgResponse = acked.length ? Math.round(acked.reduce((s, f) => s + responseSeconds(f)!, 0) / acked.length) : null;
  return { total: falls.length, open: falls.length - acked.length, byRoom, byHour, avgResponse };
}

/* ---------- date-wise history ---------- */

export const DAY = 24 * HOUR;
export const HISTORY_DAYS = 7;

/** Day start (local midnight) for `offset` days before today. */
export function dayStart(offset: number) {
  const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - offset); return d.getTime();
}

const pastCache = new Map<number, FallEvent[]>();
/** Demo history for earlier days: deterministic per calendar day, all attended. */
export function pastFalls(offset: number): FallEvent[] {
  const start = dayStart(offset);
  const cached = pastCache.get(start); if (cached) return cached;
  const r = rand((Math.floor(start / DAY) * 2654435761) % 2147483647 || 1);
  for (let i = 0; i < 5; i++) r(); // decorrelate neighbouring days
  const weights = [3, 1, 4, 1, 1, 5, 1, 2];
  const pool = RESIDENTS_SEED.flatMap((res, i) => Array(weights[i]).fill(res));
  const count = 4 + Math.floor(r() * 9);
  const list = Array.from({ length: count }, (_, i) => {
    const res = pool[Math.floor(r() * pool.length)];
    const at = start + Math.floor(r() * (DAY - 10 * MIN));
    const ack = at + Math.floor((35 + r() * 280) * 1000);
    const notes = ['No injury, helped up', 'Minor injury, first aid given', 'Nurse assessment requested', 'False alarm'];
    return { id: `f-${start}-${i}`, residentId: res.id, room: res.room, wing: res.wing, at, confidence: 0.6 + r() * 0.38,
      acknowledgedAt: ack, acknowledgedBy: 'Nurse on duty', note: notes[Math.floor(r() * notes.length)], clipSeed: Math.floor(r() * 1e6) };
  }).sort((a, b) => b.at - a.at);
  pastCache.set(start, list);
  return list;
}

export const fallsForDay = (offset: number, today: FallEvent[]) => offset === 0 ? today : pastFalls(offset);

export function dayLabel(offset: number, long = false) {
  if (offset === 0) return 'Today';
  if (offset === 1) return 'Yesterday';
  return new Date(dayStart(offset)).toLocaleDateString([], long ? { weekday: 'long', day: 'numeric', month: 'long' } : { weekday: 'short' });
}
