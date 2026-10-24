/** Manager-console state for behaviour alerts: today's events, staff checks and new-alert toasts. */
import { useEffect, useRef, useState } from 'react';
import type { BehaviourEvent } from '../types';
import { dayStart } from './data';

const CHECKED_KEY = 'icare.behaviour.checked';

function loadChecked(): Set<string> {
  try { return new Set(JSON.parse(localStorage.getItem(CHECKED_KEY) ?? '[]') as string[]); } catch { return new Set(); }
}

/** Today's events plus which ones staff have marked as checked (kept in this browser). */
export function useBehaviourDesk(events: BehaviourEvent[] | null) {
  const [checked, setChecked] = useState<Set<string>>(loadChecked);
  const today = (events ?? []).filter(e => Date.parse(e.created_at_utc) >= dayStart(0));
  const open = today.filter(e => !checked.has(e.event_id));
  function check(id: string) {
    setChecked(previous => {
      const next = new Set(previous).add(id);
      try { localStorage.setItem(CHECKED_KEY, JSON.stringify([...next].slice(-500))); } catch { /* storage unavailable */ }
      return next;
    });
  }
  return { today, open, checked, check };
}

/** Events first seen in this console, created in the last two minutes (older ones are history). */
export function useNewBehaviour(events: BehaviourEvent[]) {
  const seen = useRef<Set<string> | null>(null);
  const [fresh, setFresh] = useState<BehaviourEvent[]>([]);
  useEffect(() => {
    if (!seen.current) { seen.current = new Set(events.map(e => e.event_id)); return; }
    const added = events.filter(e => !seen.current!.has(e.event_id));
    added.forEach(e => seen.current!.add(e.event_id));
    const recent = added.filter(e => Date.now() - Date.parse(e.created_at_utc) < 2 * 60_000);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- new events arrive from polling
    if (recent.length) setFresh(previous => [...recent, ...previous].slice(0, 4));
  }, [events]);
  const dismiss = (id: string) => setFresh(previous => previous.filter(e => e.event_id !== id));
  return { fresh, dismiss };
}
