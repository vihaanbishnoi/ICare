/** Family portal: one resident's live status, today's events, care-team messages and a daily summary. */
import { useEffect, useRef, useState } from 'react';
import { ago, clock, dayLabel, duration, fallsForDay, HISTORY_DAYS, markRead, responseSeconds, STATUS_LABEL, useNow, useStore, type FallEvent, type Session } from './data';
import { downloadCsv, printReport } from './report';
import { FallClip, Icon, Initials, Logo, Modal, StatusPill } from './ui';
import { BigAlert, dayChipLabels } from './extras';
import './family.css';

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
  const todayFalls = falls.filter(f => f.residentId === me.id);
  const [day, setDay] = useState(0);
  const dayCounts = Array.from({ length: HISTORY_DAYS }, (_, i) => fallsForDay(i, falls).filter(f => f.residentId === me.id).length);
  const myFalls = day === 0 ? todayFalls : fallsForDay(day, falls).filter(f => f.residentId === me.id);
  const [bigFall, setBigFall] = useState<FallEvent | null>(null);
  const openFall = todayFalls.find(f => !f.acknowledgedAt);
  const inbox = messages.filter(m => m.residentId === me.id || m.residentId === 'all');
  const unread = inbox.filter(m => !m.read).length;
  const [clip, setClip] = useState<FallEvent | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Tell the family as soon as something new arrives for their parent.
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => {
    const ids = [...todayFalls.map(f => f.id), ...inbox.map(m => m.id)];
    if (!seen.current) { seen.current = new Set(ids); return; }
    const freshFall = todayFalls.find(f => !seen.current!.has(f.id));
    const freshMsg = inbox.find(m => !seen.current!.has(m.id));
    ids.forEach(id => seen.current!.add(id));
    if (freshFall) setBigFall(freshFall);
    else if (freshMsg) setToast(`New message from the care team: ${freshMsg.title}`);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [falls, messages]);
  useEffect(() => { if (!toast) return; const t = window.setTimeout(() => setToast(null), 7000); return () => window.clearTimeout(t); }, [toast]);

  const timeline = [
    ...myFalls.flatMap(f => [
      { at: f.at, kind: 'fall', title: 'Fall detected', text: `Room ${f.room}. Staff alerted automatically.`, fall: f },
      ...(f.acknowledgedAt ? [{ at: f.acknowledgedAt, kind: 'ok', title: 'Staff attended', text: `${f.note ?? 'Checked on'} · within ${duration(responseSeconds(f)!)}`, fall: f }] : []),
    ]),
    ...(day === 0 && me.status !== 'fall' ? [{ at: me.since, kind: me.status, title: STATUS_LABEL[me.status], text: STATUS_COPY[me.status], fall: undefined }] : []),
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
      <section className="p-fhero" data-status={me.status}>
        <div className="p-fhero__top">
          <div className="p-fhero__who">
            <span className="p-hero__avatar"><Initials name={me.name} tone={Number(me.id.slice(1))} /><span className="p-hero__ring" /></span>
            <div>
              <p className="p-fhero__eyebrow">Your parent</p>
              <h1>{me.name}</h1>
              <div className="p-fhero__tags"><span>{me.age} years</span><span>Room {me.room}</span><span>{me.wing} wing</span></div>
            </div>
          </div>
          <div className="p-fhero__status">
            <StatusPill status={me.status} />
            <strong>{STATUS_COPY[me.status]}</strong>
            <small>Since {clock(me.since)} · updated {ago(now - 2000, now)}</small>
          </div>
        </div>

        {openFall && <div className="p-fhero__alert" role="alert">
          <span className="p-fhero__alerticon"><Icon name="alert" size={18} /></span>
          <div><strong>Staff are on their way</strong>
            <p>Fall detected at {clock(openFall.at)} in room {openFall.room}. We'll message you once they've checked on {me.name.split(' ')[0]}.</p></div>
          <button type="button" className="p-btn p-btn--sm" onClick={() => setClip(openFall)}><Icon name="play" size={14} />View clip</button>
        </div>}

        <dl className="p-fhero__stats">
          <div><dt>Falls today</dt><dd className="num">{todayFalls.length}</dd></div>
          <div><dt>Avg staff response</dt><dd className="num">{(() => { const a = todayFalls.filter(f => f.acknowledgedAt); return a.length ? duration(Math.round(a.reduce((s, f) => s + responseSeconds(f)!, 0) / a.length)) : '–'; })()}</dd></div>
          <div><dt>Last fall</dt><dd className="num">{todayFalls.length ? clock(Math.max(...todayFalls.map(f => f.at))) : 'None today'}</dd></div>
          <div><dt>Monitoring</dt><dd><span className="p-live-dot" />On, 24/7</dd></div>
        </dl>
      </section>

      <div className="p-fgrid">
        <section className="p-card p-factivity">
          <header className="p-factivity__head">
            <div><h2>Activity</h2><p className="p-muted p-small">{dayLabel(day, true)} · {myFalls.length} {myFalls.length === 1 ? 'fall' : 'falls'}</p></div>
            <div className="p-factivity__dl">
              <button type="button" className="p-btn p-btn--sm" onClick={() => printReport(myFalls, residents, `Daily summary · ${me.name} · ${dayLabel(day, true)}`)}><Icon name="download" size={14} />PDF</button>
              <button type="button" className="p-btn p-btn--sm" onClick={() => downloadCsv(myFalls, residents, me.name.split(' ')[0].toLowerCase())}>CSV</button>
            </div>
          </header>
          <div className="p-fdays" role="tablist" aria-label="Choose a day">
            {dayChipLabels(HISTORY_DAYS).map((l, i) => <button key={i} type="button" role="tab" aria-selected={day === i}
              data-on={day === i ? 'true' : undefined} onClick={() => setDay(i)}>
              <span>{l.short}</span><b className="num" data-zero={dayCounts[i] ? undefined : 'true'}>{dayCounts[i]}</b>
            </button>)}
          </div>
          <ol className="p-timeline">{timeline.map((e, i) => <li key={i} data-kind={e.kind}>
            <span className="p-timeline__dot" />
            <div><strong>{e.title}</strong><p>{e.text}</p><small className="p-muted num">{clock(e.at)} · {ago(e.at, now)}</small></div>
            {e.fall && e.kind === 'fall' && <button type="button" className="p-btn p-btn--sm" onClick={() => setClip(e.fall!)}><Icon name="play" size={14} />Clip</button>}
          </li>)}
            {!timeline.length && <li className="p-empty p-fempty"><Icon name="check" />No falls on this day. Monitoring ran normally.</li>}</ol>
        </section>

        <section className="p-card p-fmsgs">
          <header className="p-factivity__head">
            <div><h2>Care team {unread > 0 && <span className="p-badge" data-tone="bad">{unread} new</span>}</h2><p className="p-muted p-small">Updates and notices</p></div>
            {unread > 0 && <button type="button" className="p-link p-small" onClick={() => markRead(me.id)}>Mark all read</button>}
          </header>
          <ul className="p-fmsgs__list">{inbox.map(m => <li key={m.id} data-unread={!m.read ? 'true' : undefined} data-kind={m.kind}>
            <span className="p-fmsgs__icon"><Icon name={m.kind === 'alert' ? 'alert' : m.kind === 'visit' ? 'clock' : 'message'} size={16} /></span>
            <div><strong>{m.title}</strong><p>{m.body}</p><small>{m.from} · {ago(m.at, now)}</small></div></li>)}
            {!inbox.length && <li className="p-empty">No messages yet.</li>}</ul>
        </section>
      </div>
    </main>

    {toast && <div className="p-toasts" aria-live="polite"><div className="p-toast"><span className="p-toast__pulse"><Icon name="bell" /></span>
      <div className="p-toast__body"><strong>{toast}</strong></div>
      <button type="button" className="p-iconbtn p-iconbtn--dark" aria-label="Dismiss" onClick={() => setToast(null)}><Icon name="close" size={16} /></button></div></div>}

    {bigFall && !clip && <BigAlert kicker="Fall detected" place={me.name.split(' ')[0]}
      detail={`A fall was detected in room ${bigFall.room}. Care staff were alerted instantly and are on their way.`}
      time={`${clock(bigFall.at)} · ${ago(bigFall.at, now)}`} extra={`Room ${bigFall.room} · ${bigFall.wing} wing`}
      primary="OK, keep me updated" onPrimary={() => setBigFall(null)}
      secondary="View clip" onSecondary={() => { const f = bigFall; setBigFall(null); setClip(f); }}
      onDismiss={() => setBigFall(null)} />}

    {clip && <Modal title={`Fall clip · ${clock(clip.at)}`} onClose={() => setClip(null)} wide>
      <FallClip fall={clip} label="Simulated clip of the detected fall" />
      <div className="p-clipmeta">
        <div><span>Room</span><strong>{clip.room}</strong></div>
        <div><span>Detected</span><strong>{clock(clip.at)}</strong></div>
        <div><span>Staff</span><strong>{clip.acknowledgedAt ? `Attended in ${duration(responseSeconds(clip)!)}` : 'On the way'}</strong></div>
        <div><span>Outcome</span><strong>{clip.note ?? 'Pending'}</strong></div>
      </div>
    </Modal>}
  </div>;
}
