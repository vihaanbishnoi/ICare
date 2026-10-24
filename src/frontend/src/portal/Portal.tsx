/** Care portal entry: sign in, then route to the family or manager experience. */
import { useState } from 'react';
import { loadSession, saveSession, type Session } from './data';
import { Family } from './Family';
import { Login } from './Login';
import { Manager } from './Manager';
import './portal.css';

export function Portal() {
  const [session, setSession] = useState<Session | null>(loadSession);
  const signIn = (s: Session) => { saveSession(s); setSession(s); };
  const signOut = () => { saveSession(null); setSession(null); };
  return <div className="portal">
    {!session ? <Login onSignIn={signIn} />
      : session.role === 'manager' ? <Manager session={session} onSignOut={signOut} />
      : <Family session={session} onSignOut={signOut} />}
  </div>;
}
