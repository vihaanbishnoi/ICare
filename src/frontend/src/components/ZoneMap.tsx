/** Every recorded fall as a soft red spot over the room photo: spots overlap where falls cluster. */
import { useEffect, useRef } from 'react';
import { LANDING_RGB, ONSET_RGB, type Layer } from '../lib/zone';
import type { DangerZone } from '../types';

const MAP_WIDTH = 960;

export function ZoneMap({ zone, layer = 'onset' }: { zone: DangerZone; layer?: Layer }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const aspect = zone.frame_width && zone.frame_height ? zone.frame_height / zone.frame_width : 9 / 16;
  const height = Math.round(MAP_WIDTH * aspect);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (!element || !context) return;
    context.clearRect(0, 0, element.width, element.height);
    const spot = (x: number, y: number, bodyWidth: number, rgb: string, alpha: number) => {
      const cx = x * element.width, cy = y * element.height;
      const radius = Math.min(0.12, Math.max(0.035, bodyWidth * 0.7)) * element.width;
      const gradient = context.createRadialGradient(cx, cy, 0, cx, cy, radius);
      gradient.addColorStop(0, `rgba(${rgb}, ${alpha})`);
      gradient.addColorStop(1, `rgba(${rgb}, 0)`);
      context.fillStyle = gradient;
      context.beginPath(); context.arc(cx, cy, radius, 0, Math.PI * 2); context.fill();
    };
    const dot = (x: number, y: number, rgb: string) => {
      context.beginPath(); context.arc(x * element.width, y * element.height, 5, 0, Math.PI * 2);
      context.fillStyle = `rgb(${rgb})`; context.fill();
      context.lineWidth = 2; context.strokeStyle = '#fff'; context.stroke();
    };
    for (const fall of zone.falls) {
      // An onset that could not be estimated repeats the landing point, so it is drawn fainter.
      if (layer !== 'landing') spot(fall.onset_x, fall.onset_y, fall.body_width, ONSET_RGB, fall.onset_estimated ? 0.4 : 0.18);
      if (layer !== 'onset') spot(fall.landing_x, fall.landing_y, fall.body_width, LANDING_RGB, 0.3);
    }
    for (const fall of zone.falls) {
      if (layer !== 'landing') dot(fall.onset_x, fall.onset_y, ONSET_RGB);
      if (layer !== 'onset') dot(fall.landing_x, fall.landing_y, LANDING_RGB);
    }
  }, [zone, layer, height]);

  return <div className="zonemap" style={{ aspectRatio: `${MAP_WIDTH} / ${height}` }}>
    {zone.photo_url
      ? <img src={zone.photo_url} alt={`Room ${zone.room} as the fixed camera sees it`} />
      : <div className="zonemap__blank">No room photo yet. It is taken from the first frame with nobody in it.</div>}
    <canvas ref={canvas} width={MAP_WIDTH} height={height} role="img"
      aria-label={`${zone.falls.length} recorded fall positions overlaid on the room`} />
  </div>;
}
