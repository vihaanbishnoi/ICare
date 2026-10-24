import type { Pose } from '../types';
import { personColor, personName } from './people';

/** Canvas text uses the page's numeric face, falling back to the system monospace. */
export const MONO = '"Atkinson Hyperlegible Mono", ui-monospace, monospace';
const ALERT = '#f87171';

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

/**
 * One person's box, skeleton and label. ``falling`` marks a recorded incident for
 * this person; ``probability`` is their latest P(Fall), shown in the label.
 */
export function drawPose(ctx: CanvasRenderingContext2D, pose: Pose, scaleX: number, scaleY: number,
                         falling: boolean, probability: number | null = null) {
  const color = falling ? ALERT : personColor(pose.track_id);
  const [x1, y1, x2, y2] = pose.bbox_xyxy.map((v, i) => i % 2 === 0 ? v * scaleX : v * scaleY);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 3]);
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.setLineDash([]);

  const reading = probability === null ? '' : `${falling ? 'fall ' : ''}${probability.toFixed(2)}`;
  const label = reading ? `${personName(pose.track_id)}: ${reading}` : `${personName(pose.track_id)}${falling ? ': fall' : ''}`;
  ctx.font = `600 12px ${MONO}`;
  const width = ctx.measureText(label).width + 10;
  const top = Math.max(y1 - 20, 0);
  ctx.fillStyle = 'rgba(8,14,13,0.78)';
  ctx.fillRect(x1, top, width, 18);
  ctx.fillStyle = color;
  ctx.fillText(label, x1 + 5, top + 13);

  const kp = pose.keypoints;
  ctx.lineCap = 'round';
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  SKELETON.forEach(([a, b]) => {
    if (kp[a][2] > 0.3 && kp[b][2] > 0.3) {
      ctx.beginPath();
      ctx.moveTo(kp[a][0] * scaleX, kp[a][1] * scaleY);
      ctx.lineTo(kp[b][0] * scaleX, kp[b][1] * scaleY);
      ctx.stroke();
    }
  });
  ctx.fillStyle = color;
  kp.forEach(([x, y, c]) => {
    if (c > 0.3) {
      ctx.beginPath();
      ctx.arc(x * scaleX, y * scaleY, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  });
}
