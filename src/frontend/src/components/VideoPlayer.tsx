/**
 * Recorded video with a canvas overlay: every person's nearest sampled pose, labelled
 * with their own latest prediction. Poses are scaled from source pixels; a person is
 * not drawn where they have no pose.
 */
import { useEffect, useRef } from 'react';
import type { Incident, Pose, Prediction } from '../types';
import { personKey } from '../lib/people';
import { hasRecordedIncident, posesAtTime, predictionsAtTime } from '../lib/playback';
import { drawPose } from '../lib/poseOverlay';

interface Props {
  mediaUrl: string;
  frameWidth: number;
  frameHeight: number;
  poses: Pose[];
  predictions: Prediction[];
  incidents: Incident[];
  onTimeChange?: (seconds: number) => void;
}

export function VideoPlayer({ mediaUrl, frameWidth, frameHeight, poses, predictions, incidents, onTimeChange }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    function drawOverlay() {
      if (!video || !canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const dw = canvas.width;
      const dh = canvas.height;
      ctx.clearRect(0, 0, dw, dh);

      const t = video.currentTime;
      const scaleX = dw / frameWidth;
      const scaleY = dh / frameHeight;
      const latest = predictionsAtTime(predictions, t);
      for (const pose of posesAtTime(poses, t)) {
        drawPose(ctx, pose, scaleX, scaleY, hasRecordedIncident(incidents, t, pose.track_id),
          latest.get(personKey(pose.track_id))?.fall_probability ?? null);
      }

      rafRef.current = requestAnimationFrame(drawOverlay);
    }

    const sync = () => {
      if (canvas && video) {
        canvas.width = video.clientWidth || 640;
        canvas.height = video.clientHeight || 360;
      }
    };

    video.addEventListener('loadedmetadata', sync);
    const observer = new ResizeObserver(sync);
    observer.observe(video);
    sync();
    rafRef.current = requestAnimationFrame(drawOverlay);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      video.removeEventListener('loadedmetadata', sync);
      observer.disconnect();
    };
  }, [mediaUrl, frameWidth, frameHeight, poses, predictions, incidents]);

  return <figure className="stage">
    <div className="stage__frame">
      <video ref={videoRef} className="stage__media" src={mediaUrl} controls playsInline
        onTimeUpdate={event => onTimeChange?.(event.currentTarget.currentTime)}
        onSeeked={event => onTimeChange?.(event.currentTarget.currentTime)}
        onLoadedMetadata={event => onTimeChange?.(event.currentTarget.currentTime)} />
      <canvas ref={canvasRef} className="stage__overlay" aria-hidden="true" />
    </div>
    <figcaption className="stage__caption"><span>Your video with each person's analyzed skeleton</span></figcaption>
  </figure>;
}
