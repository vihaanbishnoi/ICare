/** Local inference dashboard, or the static public site when built with --mode static. */
import { useEffect, useState } from 'react';
import { Brand, ModeTabs, ThemeToggle, type Mode } from './components/Chrome';
import { LivePanel } from './components/LivePanel';
import { PublicSite } from './components/PublicSite';
import { UploadPanel } from './components/UploadPanel';
import { STATIC_DEMO } from './config';

const initialMode = (): Mode => (window.location.hash === '#video' ? 'video' : 'live');

function LocalDashboard() {
  const [mode, setMode] = useState<Mode>(initialMode);
  useEffect(() => {
    // Back/forward and edited URLs switch modes too.
    const follow = () => setMode(initialMode());
    window.addEventListener('hashchange', follow);
    return () => window.removeEventListener('hashchange', follow);
  }, []);
  function choose(next: Mode) {
    setMode(next);
    window.history.replaceState(null, '', `#${next}`);
  }
  return <>
    <header className="topbar">
      <Brand />
      <ModeTabs mode={mode} onChange={choose} prefix="local" label="Detection mode" />
      <ThemeToggle />
    </header>
    <main className="page">
      <section role="tabpanel" id="local-panel-live" aria-labelledby="local-tab-live" hidden={mode !== 'live'}>
        {/* Unmounting stops the camera and releases the model for video analysis. */}
        {mode === 'live' && <LivePanel />}
      </section>
      <section role="tabpanel" id="local-panel-video" aria-labelledby="local-tab-video" hidden={mode !== 'video'}>
        <UploadPanel />
      </section>
    </main>
  </>;
}

export default function App() {
  return STATIC_DEMO ? <PublicSite /> : <LocalDashboard />;
}
