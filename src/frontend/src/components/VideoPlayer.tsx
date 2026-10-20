/**
 * Recorded video with a canvas overlay for the nearest sampled pose and the latest
 * prediction. Poses are scaled from source pixels; no overlay where no pose exists.
 */
import { useEffect, useRef } from 'react';
import type { Incident, Pose, Prediction } from '../types';
import { hasRecordedIncident, poseAtTime, predictionAtTime } from '../lib/playback';
import { drawPose, MONO } from '../lib/poseOverlay';

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
      const pose = poseAtTime(poses, t);
      const pred = predictionAtTime(predictions, t);
      const falling = hasRecordedIncident(incidents, t);

      drawPose(ctx, pose, scaleX, scaleY, falling);

      // P(Fall) confidence bar (bottom-right)
      if (pred !== null) {
        const p = pred.fall_probability;
        const bX = dw - 140, bY = dh - 40, bW = 120, bH = 10;
        ctx.fillStyle = 'rgba(7,12,22,0.8)';
        ctx.beginPath();
        ctx.roundRect(bX - 8, bY - 24, bW + 16, bH + 32, 6);
        ctx.fill();
        ctx.fillStyle = 'rgba(139,148,158,0.6)';
        ctx.font = `500 11px ${MONO}`;
        ctx.fillText('P(Fall)', bX, bY - 8);
        ctx.textAlign = 'right';
        ctx.fillText(p.toFixed(2), bX + bW, bY - 8);
        ctx.textAlign = 'left';

        ctx.fillStyle = 'rgba(33,38,45,0.9)';
        ctx.beginPath();
        ctx.roundRect(bX, bY, bW, bH, 4);
        ctx.fill();
        const barColor = p >= 0.5 ? '#f85149' : p > 0.3 ? '#d29922' : '#58a6ff';
        ctx.fillStyle = barColor;
        ctx.beginPath();
        ctx.roundRect(bX, bY, bW * p, bH, 4);
        ctx.fill();

        // Threshold tick
        ctx.strokeStyle = 'rgba(139,148,158,0.4)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(bX + bW * 0.5, bY - 2);
        ctx.lineTo(bX + bW * 0.5, bY + bH + 2);
        ctx.stroke();
        ctx.fillStyle = 'rgba(139,148,158,0.4)';
        ctx.font = `400 9px ${MONO}`;
        ctx.textAlign = 'center';
        ctx.fillText('0.5', bX + bW * 0.5, bY + bH + 12);
        ctx.textAlign = 'left';
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
    <figcaption className="stage__caption"><span>Your video with the analyzed skeleton</span></figcaption>
  </figure>;
}
