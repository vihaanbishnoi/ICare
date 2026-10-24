import { useState } from 'react';

const KEY = 'icare-room';

/** The room the fixed camera watches, remembered between visits. '' means no room. */
export function useRoomChoice(): [string, (room: string) => void] {
  const [room, setRoom] = useState(() => {
    try { return localStorage.getItem(KEY) ?? ''; } catch { return ''; }
  });
  const choose = (next: string) => {
    setRoom(next);
    try { localStorage.setItem(KEY, next); } catch { /* storage unavailable: the choice lasts for this page */ }
  };
  return [room, choose];
}
