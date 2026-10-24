/** Two sign-in paths: family members see one resident, care managers see the facility. */
import { useState, type FormEvent } from 'react';
import { DEMO_RESIDENTS, type Role, type Session } from './data';
import { Icon, Logo } from './ui';

export const MANAGER = { email: 'manager@icare.demo', name: 'Aayush' };

export function Login({ onSignIn }: { onSignIn: (s: Session) => void }) {
  const [role, setRole] = useState<Role>('family');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  function submit(e: FormEvent) {
    e.preventDefault();
    const value = email.trim().toLowerCase();
    if (!value || !password) { setError('Enter your email and password.'); return; }
    if (role === 'manager') {
      if (value !== MANAGER.email) { setError('No care manager account uses that email. Try the demo account below.'); return; }
      onSignIn({ role, name: MANAGER.name, email: value });
      return;
    }
    const res = DEMO_RESIDENTS.find(r => r.familyEmail === value);
    if (!res) { setError('That email is not linked to a resident. Ask the care home to add you, or use a demo account.'); return; }
    onSignIn({ role, name: res.family, email: value, residentId: res.id });
  }

  function fillDemo() {
    setError('');
    setEmail(role === 'manager' ? MANAGER.email : DEMO_RESIDENTS[0].familyEmail);
    setPassword('demo-password');
  }

  return <div className="p-login">
    <section className="p-login__art" aria-hidden="true">
      <Logo />
      <div className="p-login__pitch">
        <h1>Peace of mind,<br />in real time.</h1>
        <p>Fall detection for care homes. Families see how their parent is doing; staff are alerted the moment someone falls.</p>
      </div>
      <div className="p-login__cards">
        <div className="p-login__card"><span className="p-status" data-status="active"><span className="p-status__dot" />Active</span><strong>Margaret · Room 101</strong><small>Moving around · updated 4s ago</small></div>
        <div className="p-login__card p-login__card--alert"><span className="p-status" data-status="fall"><span className="p-status__dot" />Fall alert</span><strong>Room 204 · East wing</strong><small>Staff notified · 0:42 to respond</small></div>
      </div>
    </section>

    <section className="p-login__form">
      <form onSubmit={submit} noValidate>
        <h2>Sign in</h2>
        <p className="p-muted">Choose how you use ICare.</p>

        <div className="p-roles" role="radiogroup" aria-label="Account type">
          {([['family', 'Family member', 'See your parent’s live status and updates', 'heart'],
             ['manager', 'Care manager', 'Monitor every room, alerts and reports', 'grid']] as const).map(([id, title, sub, icon]) =>
            <label key={id} className="p-role" data-checked={role === id ? 'true' : undefined}>
              <input type="radio" name="role" value={id} checked={role === id} onChange={() => { setRole(id); setError(''); }} />
              <span className="p-role__icon"><Icon name={icon} /></span>
              <span><strong>{title}</strong><small>{sub}</small></span>
            </label>)}
        </div>

        <label className="p-field"><span>Email</span>
          <input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}
            placeholder={role === 'manager' ? 'you@carehome.com' : 'you@example.com'} aria-invalid={!!error} />
        </label>
        <label className="p-field"><span>Password</span>
          <input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" />
        </label>

        {error && <p className="p-error" role="alert">{error}</p>}

        <button type="submit" className="p-btn p-btn--primary p-btn--block">
          {role === 'manager' ? 'Sign in to care console' : 'Sign in to family portal'}
        </button>

        <div className="p-demo">
          <span>Demo environment</span>
          <button type="button" className="p-link" onClick={fillDemo}>Use demo {role === 'manager' ? 'manager' : 'family'} account</button>
        </div>
      </form>
    </section>
  </div>;
}
