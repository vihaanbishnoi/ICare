import { readdirSync } from 'node:fs';
import { join } from 'node:path';

/** The recorded demonstration of the earlier YOLO Tiny + RTMPose iteration. */
export const DEMO_VIDEO = 'demo.mp4';

/** A static build fails rather than publishing an unapproved file from public/. */
export function validatePublicAssets(root: string): void {
  const required = new Set(['favicon.svg', DEMO_VIDEO]);
  const optional = new Set<string>();
  function visit(directory: string, prefix = '') {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const name = `${prefix}${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error(`Public symlinks are not allowed: ${name}`);
      if (entry.isDirectory()) visit(join(directory, entry.name), `${name}/`);
      else if (!required.delete(name) && !optional.delete(name)) throw new Error(`Unapproved public asset: ${name}`);
    }
  }
  visit(root);
  if (required.size) throw new Error(`Missing approved public assets: ${[...required].join(', ')}`);
}
