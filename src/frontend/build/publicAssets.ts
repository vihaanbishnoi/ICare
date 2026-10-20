import { readdirSync } from 'node:fs';
import { join } from 'node:path';

/** A static build fails rather than publishing an unapproved file from public/. */
export function validatePublicAssets(root: string): void {
  const allowed = new Set(['favicon.svg']);
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
