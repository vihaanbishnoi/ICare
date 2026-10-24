/** Family portal: one resident's live status, today's events, care-team messages and a daily summary. */
import { useEffect, useRef, useState } from 'react';
import { ago, clock, duration, markRead, responseSeconds, STATUS_LABEL, useNow, useStore, type FallEvent, type Session } from './data';
import { downloadCsv, printReport } from './report';
import { ClipPlayer, Icon, Initials, Logo, Modal, StatusPill } from './ui';

const STATUS_COPY = {
  active: 'Up and moving around',
  resting: 'Resting comfortably',
  away: 'Out of their room, likely in a common area',
  fall: 'A fall was detected. Staff have been alerted.',
};

export function Family({ session, onSignOut }: { session: Session; onSignOut: () => void }) {
  const { residents, falls, messages } = useStore();
  const now = useNow(1000);
  const me = residents.find(r => r.id === session.residentId)!;
  const myFalls = falls.filter(f => f.residentId === me.id);
  const openFall = myFalls.find(f => !f.acknowledgedAt);
  const inbox = messages.filter(m => m.residentId === me.id || m.residentId === 'all');
  const unread = inbox.filter(m => !m.read).length;
  const [clip, setClip] = useState<FallEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Tell the family as soon as something new arrives for their parent.
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    const ids = [...myFalls.map(f => f.id), ...inbox.map(m => m.id)];
    if (!seen.current) { seen.current = new Set(ids); return; }
    const freshFall = myFalls.find(f => !seen.current!.has(f.id));
    const freshMsg = inbox.find(m => !seen.current!.has(m.id));
    ids.forEach(id => seen.current!.add(id));
    if (freshFall) setToast(`A fall was detected in room ${freshFall.room}. Staff are responding.`);
    else if (freshMsg) setToast(`New message from the care team: ${freshMsg.title}`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [falls, messages]);
  useEffect(() => { if (!toast) return; const t = window.setTimeout(() => setToast(null), 7000); return () => window.clearTimeout(t); }, [toast]);

  const timeline = [
    ...myFalls.flatMap(f => [
      { at: f.at, kind: 'fall', title: 'Fall detected', text: `Room ${f.room}. Staff alerted automatically.`, fall: f },
      ...(f.acknowledgedAt ? [{ at: f.acknowledgedAt, kind: 'ok', title: 'Staff attended', text: `${f.note ?? 'Checked on'} · within ${duration(responseSeconds(f)!)}`, fall: f }] : []),
    ]),
    { at: me.since, kind: me.status, title: STATUS_LABEL[me.status], text: STATUS_COPY[me.status], fall: undefined },
  ].sort((a, b) => b.at - a.at);

  return <div className="p-family">
    <header className="p-fam-top">
      <Logo />
      <div className="p-fam-top__right">
        <span className="p-chip"><span className="p-live-dot" />Live</span>
        <div className="p-user p-user--compact">
          <Initials name={session.name} tone={3} />
          <div><strong>{session.name}</strong><small>Family of {me.name.split(' ')[0]}</small></div>
          <button type="button" className="p-iconbtn" onClick={onSignOut} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button>
        </div>
      </div>
    </header>

    <main className="p-fam-main">
      {openFall && <div className="p-banner" role="alert">
        <span className="p-toast__pulse"><Icon name="alert" /></span>
        <div><strong>A fall was detected at {clock(openFall.at)}</strong><p>Care staff were alerted instantly and are on their way. We'll message you as soon as they've checked on {me.name.split(' ')[0]}.</p></div>
        <button type="button" className="p-btn p-btn--sm" onClick={() => setClip(openFall)}><Icon name="play" size={14} />View clip</button>
      </div>}

      <section className="p-hero" data-status={me.status}>
        <div className="p-hero__who">
          <span className="p-hero__avatar"><Initials name={me.name} tone={Number(me.id.slice(1))} /><span className="p-hero__ring" /></span>
          <div><p className="p-muted">Live status</p><h1>{me.name}</h1><p className="p-muted">{me.age} years · Room {me.room} · {me.wing} wing</p></div>
        </div>
        <div className="p-hero__status">
          <StatusPill status={me.status} />
          <strong>{STATUS_COPY[me.status]}</strong>
          <small className="p-muted">Since {clock(me.since)} · updated {ago(now - 2000, now)}</small>
        </div>
      </section>

      <div className="p-fam-grid">
        <section className="p-card">
          <header className="p-card__head"><span>Today</span></header>
          <div className="p-fam-stats">
            <div><span>Falls</span><strong className="num">{myFalls.length}</strong></div>
            <div><span>Staff response</span><strong className="num">{(() => { const a = myFalls.filter(f => f.acknowledgedAt); return a.length ? duration(Math.round(a.reduce((s, f) => s + responseSeconds(f)!, 0) / a.length)) : '–'; })()}</strong></div>
            <div><span>Monitoring</span><strong>On</strong></div>
          </div>
          <div className="p-quick">
            <button type="button" className="p-btn p-btn--block" onClick={() => printReport(myFalls, residents, `Daily summary · ${me.name}`)}><Icon name="download" size={16} />Download today's summary</button>
            <button type="button" className="p-btn p-btn--block p-btn--quiet" onClick={() => downloadCsv(myFalls, residents, me.name.split(' ')[0].toLowerCase())}>Export as CSV</button>
          </div>
        </section>

        <section className="p-card p-span-2-md">
          <header className="p-card__head"><span>Activity</span><span className="p-muted p-small">Today</span></header>
          <ol className="p-timeline">{timeline.map((e, i) => <li key={i} data-kind={e.kind}>
            <span className="p-timeline__dot" />
            <div><strong>{e.title}</strong><p>{e.text}</p><small className="p-muted num">{clock(e.at)} · {ago(e.at, now)}</small></div>
            {e.fall && e.kind === 'fall' && <button type="button" className="p-btn p-btn--sm" onClick={() => setClip(e.fall!)}><Icon name="play" size={14} />5s clip</button>}
          </li>)}</ol>
        </section>

        <section className="p-card p-span-3">
          <header className="p-card__head"><span>Messages from the care team {unread > 0 && <span className="p-badge" data-tone="bad">{unread} new</span>}</span>
            {unread > 0 && <button type="button" className="p-btn p-btn--sm" onClick={() => markRead(me.id)}>Mark all read</button>}</header>
          <ul className="p-msgs">{inbox.map(m => <li key={m.id} data-unread={!m.read ? 'true' : undefined}>
            <span className="p-badge" data-tone={m.kind === 'alert' ? 'bad' : m.kind === 'visit' ? 'info' : 'good'}>{m.kind === 'alert' ? 'Fall' : m.kind}</span>
            <div><strong>{m.title}</strong><p>{m.body}</p><small className="p-muted">{m.from} · {ago(m.at, now)}</small></div></li>)}
            {!inbox.length && <li className="p-empty">No messages yet.</li>}</ul>
        </section>
      </div>
    </main>

    {toast && <div className="p-toasts" aria-live="polite"><div className="p-toast"><span className="p-toast__pulse"><Icon name="bell" /></span>
      <div className="p-toast__body"><strong>{toast}</strong></div>
      <button type="button" className="p-iconbtn p-iconbtn--dark" aria-label="Dismiss" onClick={() => setToast(null)}><Icon name="close" size={16} /></button></div></div>}

    {clip && <Modal title={`Fall clip · ${clock(clip.at)}`} onClose={() => setClip(null)} wide>
      <ClipPlayer seed={clip.clipSeed} room={clip.room} at={clip.at} label="Five second clip of the detected fall" />
      <div className="p-clipmeta">
        <div><span>Room</span><strong>{clip.room}</strong></div>
        <div><span>Detected</span><strong>{clock(clip.at)}</strong></div>
        <div><span>Staff</span><strong>{clip.acknowledgedAt ? `Attended in ${duration(responseSeconds(clip)!)}` : 'On the way'}</strong></div>
        <div><span>Outcome</span><strong>{clip.note ?? 'Pending'}</strong></div>
      </div>
    </Modal>}
  </div>;
}
