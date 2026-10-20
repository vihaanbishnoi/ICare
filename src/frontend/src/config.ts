/** Vite resolves these at build time; static mode never mounts local controls. */
export const STATIC_DEMO = import.meta.env.MODE === 'static';

declare const __DEMO_VIDEO__: boolean;
/** Whether public/demo.mp4 existed when the static site was built. */
export const HAS_DEMO_VIDEO = __DEMO_VIDEO__;
