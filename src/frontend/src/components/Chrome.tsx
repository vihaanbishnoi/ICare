/** Header pieces shared by the local dashboard and the static site. */
import type { KeyboardEvent } from 'react';
import { useTheme } from '../lib/theme';

export type Mode = 'live' | 'video';

const MODES: { id: Mode; label: string }[] = [
  { id: 'live', label: 'Live detection' },
  { id: 'video', label: 'Analyze video' },
];

export function Brand() {
  return <div className="brand">
    <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="7" />
      <path d="M5 18h5l2.5-6 4 11 3-8 1.5 3H27" />
    </svg>
    <span className="brand__name">ICare</span>
    <span className="brand__tag">Research prototype</span>
  </div>;
}

/** ARIA tabs: arrow keys move between modes, panels are named `${prefix}-panel-${mode}`. */
export function ModeTabs({ mode, onChange, prefix, label }: {
  mode: Mode; onChange: (mode: Mode) => void; prefix: string; label: string;
}) {
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = MODES.findIndex(item => item.id === mode);
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = MODES[(index + step + MODES.length) % MODES.length].id;
    onChange(next);
    document.getElementById(`${prefix}-tab-${next}`)?.focus();
  }
  return <div className="mode-tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
    {MODES.map(item => <button key={item.id} type="button" role="tab" id={`${prefix}-tab-${item.id}`}
      className="mode-tabs__tab" aria-selected={mode === item.id} aria-controls={`${prefix}-panel-${item.id}`}
      tabIndex={mode === item.id ? 0 : -1} onClick={() => onChange(item.id)}>{item.label}</button>)}
  </div>;
}

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const next = theme === 'dark' ? 'light' : 'dark';
  return <button type="button" className="icon-button" onClick={toggle}
    aria-label={`Switch to ${next} theme`} title={`Switch to ${next} theme`}>
    {theme === 'dark'
      ? <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" /><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" /></svg>
      : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></svg>}
  </button>;
}
