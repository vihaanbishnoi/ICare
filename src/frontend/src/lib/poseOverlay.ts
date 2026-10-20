import type { Pose } from '../types';

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

export function drawPose(ctx: CanvasRenderingContext2D, pose: Pose | null, scaleX: number, scaleY: number, falling: boolean) {
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
}
