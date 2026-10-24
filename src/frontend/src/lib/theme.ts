import { useEffect, useState } from 'react';

type Theme = 'light' | 'dark';

/** Same key as the inline script in index.html, which applies it before first paint. */
const STORAGE_KEY = 'icare-theme';
const systemDark = () => window.matchMedia('(prefers-color-scheme: dark)');

function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : null;
  } catch {
    return null;
  }
}

/** Follows the system until the person picks a theme, then remembers that choice. */
export function useTheme() {
  const [chosen, setChosen] = useState<Theme | null>(() => storedTheme() ?? 'light');
  const [system, setSystem] = useState<Theme>(() => (systemDark().matches ? 'dark' : 'light'));
  const theme = chosen ?? system;

  useEffect(() => {
    const query = systemDark();
    const update = () => setSystem(query.matches ? 'dark' : 'light');
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (chosen) document.documentElement.dataset.theme = chosen;
    else delete document.documentElement.dataset.theme;
  }, [chosen]);

  function toggle() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    setChosen(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* storage unavailable: still applies for this visit */ }
  }

  return { theme, toggle };
}
