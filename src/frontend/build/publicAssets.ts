import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { PublicExample } from '../src/types.ts';

export function demoFile(name: string, extension: string): string {
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(name) || name.includes('..') || !name.endsWith(extension)) {
    throw new Error('Public demo files must be plain filenames with the expected extension.');
  }
  return `demos/${name}`;
}

/** A static build fails rather than publishing an unapproved file from public/. */
export function validatePublicAssets(root: string): void {
  const catalog = JSON.parse(readFileSync(join(root, 'demos/catalog.json'), 'utf8'));
  const allowed = new Set(['favicon.svg', 'icons.svg', 'demos/catalog.json']);
  for (const item of catalog.examples as PublicExample[]) {
    if (item.approved !== true) throw new Error('Every published example needs explicit approval.');
    allowed.add(demoFile(item.video, '.mp4'));
    allowed.add(demoFile(item.result, '.json'));
    if (item.csv) allowed.add(demoFile(item.csv, '.csv'));
  }
  function visit(directory: string, prefix = '') {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const name = `${prefix}${entry.name}`;
      if (entry.isSymbolicLink()) throw new Error(`Public symlinks are not allowed: ${name}`);
      if (entry.isDirectory()) visit(join(directory, entry.name), `${name}/`);
      else if (!allowed.delete(name)) throw new Error(`Unapproved public asset: ${name}`);
    }
  }
  visit(root);
  if (allowed.size) throw new Error(`Missing approved public assets: ${[...allowed].join(', ')}`);
}
