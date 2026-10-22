/** Vite resolves these at build time; static mode never mounts local controls. */
export const STATIC_DEMO = import.meta.env.MODE === 'static';
