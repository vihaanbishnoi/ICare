/** Care portal entry: sign in, then route to the family or manager experience. */
import { useState } from 'react';
import { loadSession, saveSession, type Session } from './data';
import { Family } from './Family';
import { Login, MANAGER } from './Login';
import { Manager } from './Manager';
import './portal.css';
import './extras.css';
import './layout.css';

export function Portal() {
  // Older saved sign-ins keep their old name; managers always show the current account name.
  const [session, setSession] = useState<Session | null>(() => {
    const s = loadSession();
    return s?.role === 'manager' ? { ...s, name: MANAGER.name } : s;
  });
  const signIn = (s: Session) => { saveSession(s); setSession(s); };
  const signOut = () => { saveSession(null); setSession(null); };
  return <div className="portal">
    {!session ? <Login onSignIn={signIn} />
      : session.role === 'manager' ? <Manager session={session} onSignOut={signOut} />
      : <Family session={session} onSignOut={signOut} />}
  </div>;
}
