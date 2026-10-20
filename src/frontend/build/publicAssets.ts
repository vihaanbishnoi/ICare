import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

/** The recorded demonstration for the public site; optional until it is provided. */
export const DEMO_VIDEO = 'demo.mp4';

export function hasDemoVideo(root: string): boolean {
  return existsSync(join(root, DEMO_VIDEO));
}

/** A static build fails rather than publishing an unapproved file from public/. */
export function validatePublicAssets(root: string): void {
  const required = new Set(['favicon.svg']);
  const optional = new Set([DEMO_VIDEO]);
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
