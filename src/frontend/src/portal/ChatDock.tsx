/** Floating message dock: the manager messages families (shown in their portal) or care staff. */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ago, sendMessage, useStore, type Resident } from './data';
import { Icon, Initials } from './ui';

type Audience = 'family' | 'staff';
interface StaffMsg { id: string; to: string; body: string; at: number }

const STAFF_CHANNELS = ['All staff', 'Nurses on duty', 'East wing team', 'West wing team', 'Garden wing team'];
const QUICK: Record<Audience, string[]> = {
  family: ['Your parent is doing well today.', 'A fall was detected; staff attended and they are comfortable.', 'Please call us when you have a moment.'],
  staff: ['Please check on the open alert now.', 'Round of all rooms in 10 minutes, please.', 'Thanks team, alert resolved.'],
};
const STAFF_KEY = 'icare-staff-messages';

function loadStaff(): StaffMsg[] {
  try { return JSON.parse(localStorage.getItem(STAFF_KEY) ?? '[]') as StaffMsg[]; } catch { return []; }
}

export function ChatDock({ residents, from }: { residents: Resident[]; from: string }) {
  const { messages } = useStore();
  const [open, setOpen] = useState(false);
  const [aud, setAud] = useState<Audience>('family');
  const [familyTo, setFamilyTo] = useState<string>('all');
  const [staffTo, setStaffTo] = useState(STAFF_CHANNELS[0]);
  const [text, setText] = useState('');
  const [staff, setStaff] = useState<StaffMsg[]>(loadStaff);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const thread = aud === 'family'
    ? messages.filter(m => m.residentId === familyTo).map(m => ({ id: m.id, body: m.title === 'Message' ? m.body : `${m.title}: ${m.body}`, at: m.at })).reverse()
    : staff.filter(m => m.to === staffTo);

  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }); }, [thread.length, open, aud, familyTo, staffTo]);
  useEffect(() => { if (open) inputRef.current?.focus(); }, [open, aud]);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k);
  }, [open]);

  function send(e?: FormEvent) {
    e?.preventDefault();
    const body = text.trim(); if (!body) return;
    if (aud === 'family') sendMessage({ residentId: familyTo, title: 'Message', body, from, kind: 'update' });
    else {
      const next = [...staff, { id: `s-${Date.now()}`, to: staffTo, body, at: Date.now() }];
      setStaff(next);
      try { localStorage.setItem(STAFF_KEY, JSON.stringify(next.slice(-200))); } catch { /* kept for this visit */ }
    }
    setText('');
  }

  const toName = aud === 'family'
    ? familyTo === 'all' ? 'All families' : residents.find(r => r.id === familyTo)?.family ?? 'Family'
    : staffTo;

  return <>
    {open && <section className="p-dock" role="dialog" aria-label="Messages">
      <header className="p-dock__head">
        <div className="p-dock__title"><span className="p-dock__icon"><Icon name="chat" /></span>
          <div><strong>Messages</strong><small>Sent as {from}</small></div></div>
        <button type="button" className="p-iconbtn p-iconbtn--dark" aria-label="Close messages" onClick={() => setOpen(false)}><Icon name="close" size={16} /></button>
      </header>
      <div className="p-dock__tabs" role="tablist" aria-label="Send to">
        {(['family', 'staff'] as const).map(a => <button key={a} type="button" role="tab" aria-selected={aud === a}
          data-on={aud === a ? 'true' : undefined} onClick={() => setAud(a)}>
          <Icon name={a === 'family' ? 'heart' : 'users'} size={16} />{a === 'family' ? 'Families' : 'Care staff'}</button>)}
      </div>
      <label className="p-dock__to"><span>To</span>
        {aud === 'family'
          ? <select value={familyTo} onChange={e => setFamilyTo(e.target.value)}>
              <option value="all">All families ({residents.length})</option>
              {residents.map(r => <option key={r.id} value={r.id}>{r.family} · family of {r.name}</option>)}</select>
          : <select value={staffTo} onChange={e => setStaffTo(e.target.value)}>{STAFF_CHANNELS.map(c => <option key={c}>{c}</option>)}</select>}
      </label>
      <div className="p-dock__list" ref={listRef} aria-live="polite">
        {thread.length === 0 && <div className="p-dock__empty"><Initials name={toName} tone={aud === 'family' ? 3 : 1} />
          <p>No messages to <b>{toName}</b> yet.</p><small>Pick a quick reply or type below.</small></div>}
        {thread.map(m => <div key={m.id} className="p-bubble"><p>{m.body}</p><small>{ago(m.at)}</small></div>)}
      </div>
      <div className="p-dock__quick">{QUICK[aud].map(q => <button key={q} type="button" onClick={() => { setText(q); inputRef.current?.focus(); }}>{q}</button>)}</div>
      <form className="p-dock__form" onSubmit={send}>
        <textarea ref={inputRef} rows={1} value={text} placeholder={`Message ${toName}…`} aria-label={`Message ${toName}`}
          onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button type="submit" className="p-dock__send" aria-label="Send" disabled={!text.trim()}><Icon name="send" size={18} /></button>
      </form>
      {aud === 'family' && <p className="p-dock__note">Appears instantly in the family portal.</p>}
    </section>}
    <button type="button" className="p-fab" aria-label={open ? 'Close messages' : 'Open messages'} aria-expanded={open} onClick={() => setOpen(v => !v)}>
      <Icon name={open ? 'close' : 'chat'} size={24} />
    </button>
  </>;
}
