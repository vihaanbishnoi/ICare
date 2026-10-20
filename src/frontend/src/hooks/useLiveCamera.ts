import { useEffect, useRef, useState } from 'react';
import { fetchLiveHistory, sendLiveFrame, startLiveSession, stopLiveSession } from '../api/client';
import { cameraError, captureCamera, nextCameraFrame } from '../lib/camera';
import { drawPose } from '../lib/poseOverlay';
import type { LiveFrame, LiveHistory, LiveIncident, Prediction } from '../types';

interface Run {
  abort: AbortController; stream: MediaStream | null; sessionId: string | null;
}

export function useLiveCamera() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const runRef = useRef<Run | null>(null);
  const mounted = useRef(true);
  const [phase, setPhase] = useState<'idle' | 'starting' | 'running' | 'stopping'>('idle');
  const [error, setError] = useState('');
  const [frame, setFrame] = useState<LiveFrame | null>(null);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [incidents, setIncidents] = useState<LiveIncident[]>([]);
  const [history, setHistory] = useState<LiveHistory[]>([]);
  const [roundTrip, setRoundTrip] = useState<number | null>(null);

  async function refreshHistory() {
    try { const data = await fetchLiveHistory(); if (mounted.current) setHistory(data); }
    catch (e) { if (mounted.current && !runRef.current) setError(cameraError(e)); }
  }

  function detach(run: Run) {
    run.abort.abort();
    run.stream?.getTracks().forEach(track => track.stop());
    if (videoRef.current) videoRef.current.srcObject = null;
    const canvas = canvasRef.current;
    canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
  }

  async function stop() {
    const run = runRef.current;
    if (!run) return;
    runRef.current = null;
    detach(run);
    if (mounted.current) setPhase('stopping');
    try { if (run.sessionId) await stopLiveSession(run.sessionId); }
    catch (e) { if (mounted.current) setError(`${cameraError(e)} The backend also expires disconnected sessions.`); }
    finally { if (mounted.current) { setPhase('idle'); void refreshHistory(); } }
  }

  async function start() {
    if (runRef.current) return;
    const run: Run = { abort: new AbortController(), stream: null, sessionId: null };
    runRef.current = run;
    setPhase('starting'); setError(''); setFrame(null); setPredictions([]); setIncidents([]); setRoundTrip(null);
    const current = () => mounted.current && runRef.current === run && !run.abort.signal.aborted;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires localhost or HTTPS and a supported browser.');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: false,
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' } });
      if (!current()) { stream.getTracks().forEach(track => track.stop()); return; }
      run.stream = stream;
      const disconnected = () => {
        if (current()) { setError('The camera disconnected or paused. Reconnect it and start again.'); void stop(); }
      };
      stream.getVideoTracks().forEach(track => {
        track.addEventListener('ended', disconnected, { once: true });
        track.addEventListener('mute', disconnected, { once: true });
      });
      const video = videoRef.current;
      if (!video) throw new Error('Camera preview is unavailable.');
      video.srcObject = stream;
      await video.play();
      if (!current()) return;
      const session = await startLiveSession();
      run.sessionId = session.session_id;
      if (!current()) { await stopLiveSession(session.session_id); return; }
      setPhase('running');
      const origin = performance.now();
      let lastCapture = -Infinity;
      while (current()) {
        await nextCameraFrame(video, run.abort.signal);
        if (!current()) return;
        if (performance.now() - lastCapture < 1000 / 6) continue;
        const captured = performance.now();
        lastCapture = captured;
        const image = await captureCamera(video);
        if (!current()) return;
        const result = await sendLiveFrame(session.session_id, image, (captured - origin) / 1000, run.abort.signal);
        if (!current()) return;
        const bitmap = await createImageBitmap(image);
        try {
          if (!current()) return;
          const canvas = canvasRef.current;
          if (canvas) {
            canvas.width = result.frame_width; canvas.height = result.frame_height;
            const context = canvas.getContext('2d');
            if (context) {
              context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
              drawPose(context, result.pose, 1, 1, result.incident_latched);
            }
          }
        } finally { bitmap.close(); }
        if (!current()) return;
        setFrame(result); setRoundTrip(performance.now() - captured);
        if (result.prediction) setPredictions(previous => [...previous, result.prediction!].slice(-120));
        if (result.incident) setIncidents(previous => [...previous, result.incident!]);
      }
    } catch (e) {
      if (current()) { setError(cameraError(e)); await stop(); }
    }
  }

  useEffect(() => {
    mounted.current = true;
    void refreshHistory();
    const leave = () => { void stop(); };
    window.addEventListener('pagehide', leave);
    return () => { mounted.current = false; window.removeEventListener('pagehide', leave); void stop(); };
    // Resources follow this component's mount lifetime, not render-time callbacks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { videoRef, canvasRef, phase, error, frame, predictions, incidents, history,
    roundTrip, start, stop, refreshHistory };
}
