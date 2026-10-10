/**
 * VideoPlayer — real <video> with a <canvas> overlay for pose keypoints and bounding box.
 * Draws COCO-17 keypoints and bbox_xyxy scaled from frame_width/frame_height to
 * displayed video dimensions. No overlay is drawn when a frame has no matching pose.
 */
import { useEffect, useRef } from 'react';
import type { Incident, Pose, Prediction } from '../types';

// COCO-17 skeleton connections (pairs of keypoint indices)
const SKELETON: [number, number][] = [
  [0, 1], [0, 2], [1, 3], [2, 4],           // head
  [5, 6],                                     // shoulders
  [5, 7], [7, 9],                             // left arm
  [6, 8], [8, 10],                            // right arm
  [5, 11], [6, 12],                           // torso
  [11, 12],                                   // hips
  [11, 13], [13, 15],                         // left leg
  [12, 14], [14, 16],                         // right leg
];

interface Props {
  mediaUrl: string;
  frameWidth: number;
  frameHeight: number;
  poses: Pose[];
  predictions: Prediction[];
  incidents: Incident[];
  /** 'fixture' shows no pose overlay — used only while backend clips are pending */
  mode?: 'live' | 'fixture';
}

export function VideoPlayer({ mediaUrl, frameWidth, frameHeight, poses, predictions, incidents, mode = 'live' }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number | null>(null);

  // Map timestamp_seconds → closest pose (within 0.5s tolerance)
  const poseMap = (() => {
    const m = new Map<number, Pose>();
    poses.forEach(p => m.set(p.timestamp_seconds, p));
    return m;
  })();

  const closestPose = (t: number): Pose | null => {
    let best: Pose | null = null;
    let bestDelta = 0.5; // 0.5s tolerance
    poseMap.forEach((p) => {
      const d = Math.abs(p.timestamp_seconds - t);
      if (d < bestDelta) { bestDelta = d; best = p; }
    });
    return best;
  };

  const closestPrediction = (t: number): Prediction | null => {
    let best: Prediction | null = null;
    let bestDelta = 1.0;
    predictions.forEach(p => {
      const d = Math.abs(p.timestamp_seconds - t);
      if (d < bestDelta) { bestDelta = d; best = p; }
    });
    return best;
  };

  const isFallActive = (t: number): boolean =>
    incidents.some(inc =>
      t >= inc.detected_at_seconds && t < inc.detected_at_seconds + 4
    );

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    function drawOverlay() {
      if (!video || !canvas) return;
      const ctx = canvas.getContext('2d')!;
      const dw = canvas.width;
      const dh = canvas.height;
      ctx.clearRect(0, 0, dw, dh);

      if (mode === 'fixture') {
        // Draw fixture label
        ctx.fillStyle = 'rgba(251,191,36,0.85)';
        ctx.font = '500 11px "JetBrains Mono", monospace';
        ctx.fillText('⚙ DEVELOPMENT FIXTURE — labelled mock data', 8, 20);
        rafRef.current = requestAnimationFrame(drawOverlay);
        return;
      }

      const t = video.currentTime;
      const scaleX = dw / frameWidth;
      const scaleY = dh / frameHeight;
      const pose = closestPose(t);
      const pred = closestPrediction(t);
      const falling = isFallActive(t);

      if (pose) {
        // Bounding box
        const [x1, y1, x2, y2] = pose.bbox_xyxy.map((v, i) => i % 2 === 0 ? v * scaleX : v * scaleY);
        const bboxColor = falling ? 'rgba(248,113,113,0.85)' : 'rgba(34,211,238,0.6)';
        ctx.strokeStyle = bboxColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
        ctx.setLineDash([]);

        // "person" label
        ctx.fillStyle = bboxColor;
        ctx.font = '500 10px "JetBrains Mono", monospace';
        ctx.fillText('person', x1, Math.max(y1 - 4, 12));

        // Skeleton
        const kp = pose.keypoints;
        ctx.lineCap = 'round';
        const skeletonColor = falling ? 'hsl(4,85%,63%)' : 'hsl(213,85%,68%)';
        ctx.strokeStyle = skeletonColor;
        ctx.lineWidth = 2;
        ctx.shadowColor = skeletonColor;
        ctx.shadowBlur = 6;
        SKELETON.forEach(([a, b]) => {
          if (kp[a][2] > 0.3 && kp[b][2] > 0.3) {
            ctx.beginPath();
            ctx.moveTo(kp[a][0] * scaleX, kp[a][1] * scaleY);
            ctx.lineTo(kp[b][0] * scaleX, kp[b][1] * scaleY);
            ctx.stroke();
          }
        });

        // Keypoints
        ctx.shadowBlur = 0;
        kp.forEach(([x, y, c]) => {
          if (c > 0.3) {
            ctx.fillStyle = falling ? '#f87171' : '#34d399';
            ctx.beginPath();
            ctx.arc(x * scaleX, y * scaleY, 3.5, 0, Math.PI * 2);
            ctx.fill();
          }
        });
      }

      // P(Fall) confidence bar (bottom-right)
      if (pred !== null) {
        const p = pred.fall_probability;
        const bX = dw - 140, bY = dh - 40, bW = 120, bH = 10;
        ctx.fillStyle = 'rgba(7,12,22,0.8)';
        ctx.beginPath();
        ctx.roundRect(bX - 8, bY - 24, bW + 16, bH + 32, 6);
        ctx.fill();
        ctx.fillStyle = 'rgba(139,148,158,0.6)';
        ctx.font = '500 10px "JetBrains Mono", monospace';
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
        ctx.font = '400 8px "JetBrains Mono", monospace';
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
    new ResizeObserver(sync).observe(video);
    rafRef.current = requestAnimationFrame(drawOverlay);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [mediaUrl, frameWidth, frameHeight, poses, predictions, incidents, mode]);

  return (
    <div className="video-wrapper" style={{ position: 'relative' }}>
      <video
        ref={videoRef}
        className="video-player"
        src={mediaUrl}
        controls
        playsInline
        style={{ width: '100%', display: 'block', borderRadius: '8px' }}
      />
      <canvas
        ref={canvasRef}
        className="video-canvas-overlay"
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
          borderRadius: '8px',
        }}
      />
    </div>
  );
}
