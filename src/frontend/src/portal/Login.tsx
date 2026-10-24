/** Two sign-in paths: family members see one resident, care managers see the facility. */
import { useState, type FormEvent } from 'react';
import { DEMO_RESIDENTS, type Role, type Session } from './data';
import { Icon, Logo } from './ui';
import './login.css';

export const MANAGER = { email: 'manager@icare.demo', name: 'Aayush' };

// Caregiver with an older woman. Unsplash photo by National Cancer Institute (Unsplash licence).
const HERO = 'https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=1600&q=70';

const ROLES = [
  { id: 'family', title: 'Family member', sub: 'Your parent’s live status', icon: 'heart' },
  { id: 'manager', title: 'Care manager', sub: 'Every room, alert and report', icon: 'grid' },
] as const;

export function Login({ onSignIn }: { onSignIn: (s: Session) => void }) {
  const [role, setRole] = useState<Role>('family');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [show, setShow] = useState(false);
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

  return <div className="p-login p-login--v2">
    <section className="p-login__art" aria-hidden="true">
      <div className="p-login__photo" style={{ backgroundImage: `url(${HERO})` }} />
      <div className="p-login__shade" />
      <div className="p-login__top"><Logo /></div>

      <div className="p-login__pitch">
        <span className="p-login__eyebrow"><span className="p-live-dot" />Live fall detection for care homes</span>
        <h1>Peace of mind,<br /><em>in real time.</em></h1>
        <p>Families see how their parent is doing. Staff are alerted the moment someone falls, with a short clip to see what happened.</p>
        <ul className="p-login__points">
          <li><Icon name="bell" size={16} />Instant fall alerts</li>
          <li><Icon name="play" size={16} />5-second clips</li>
          <li><Icon name="report" size={16} />Daily reports</li>
        </ul>
      </div>

      <div className="p-login__stack">
        <div className="p-login__card">
          <span className="p-avatar" data-tone="0">MS</span>
          <div><strong>Margaret · Room 101</strong><small>Moving around · updated 4s ago</small></div>
          <span className="p-status" data-status="active"><span className="p-status__dot" />Active</span>
        </div>
        <div className="p-login__card p-login__card--alert">
          <span className="p-login__alerticon"><Icon name="alert" size={18} /></span>
          <div><strong>Fall detected · Room 204</strong><small>East wing · staff notified 0:42 ago</small></div>
          <span className="p-login__respond">Respond</span>
        </div>
      </div>
    </section>

    <section className="p-login__form">
      <form onSubmit={submit} noValidate>
        <div className="p-login__mobilelogo"><Logo /></div>
        <header>
          <h2>Welcome back</h2>
          <p className="p-muted">Sign in to ICare to continue.</p>
        </header>

        <div className="p-roles2" role="radiogroup" aria-label="I am a">
          {ROLES.map(r => <label key={r.id} className="p-role2" data-checked={role === r.id ? 'true' : undefined}>
            <input type="radio" name="role" value={r.id} checked={role === r.id} onChange={() => { setRole(r.id); setError(''); }} />
            <span className="p-role2__icon"><Icon name={r.icon} size={18} /></span>
            <strong>{r.title}</strong><small>{r.sub}</small>
            <span className="p-role2__check" aria-hidden="true"><Icon name="check" size={12} /></span>
          </label>)}
        </div>

        <label className="p-field"><span>Email</span>
          <span className="p-input">
            <Icon name="mail" size={16} />
            <input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)}
              placeholder={role === 'manager' ? 'you@carehome.com' : 'you@example.com'} aria-invalid={!!error} />
          </span>
        </label>
        <label className="p-field"><span>Password</span>
          <span className="p-input">
            <Icon name="lock" size={16} />
            <input type={show ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} placeholder="Your password" />
            <button type="button" className="p-input__toggle" onClick={() => setShow(v => !v)} aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show}>
              {show ? 'Hide' : 'Show'}
            </button>
          </span>
        </label>

        {error && <p className="p-error" role="alert">{error}</p>}

        <button type="submit" className="p-btn p-btn--primary p-btn--block p-btn--xl">
          {role === 'manager' ? 'Sign in to care console' : 'Sign in to family portal'}<span aria-hidden="true">→</span>
        </button>

        <div className="p-demo2">
          <span className="p-demo2__tag">Demo</span>
          <span>Try it without an account.</span>
          <button type="button" className="p-link" onClick={fillDemo}>Fill demo {role === 'manager' ? 'manager' : 'family'} login</button>
        </div>

        <p className="p-login__help">No account yet? Ask your care home to invite you.</p>
      </form>
    </section>
  </div>;
}
