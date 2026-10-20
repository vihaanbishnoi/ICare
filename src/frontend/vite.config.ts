import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import { hasDemoVideo, validatePublicAssets } from './build/publicAssets.ts'

const publicDir = fileURLToPath(new URL('./public', import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => ({
  base: mode === 'static' ? '/ICare/' : '/',
  // The public site shows public/demo.mp4 when it exists, otherwise a placeholder.
  define: { __DEMO_VIDEO__: JSON.stringify(mode === 'static' && hasDemoVideo(publicDir)) },
  plugins: [react(), ...(mode === 'static' ? [{
    name: 'approved-public-assets',
    buildStart() { validatePublicAssets(publicDir) },
  }] : [])],
  server: mode === 'static' ? {} : {
    // During development: proxy /api/v1 → backend so relative URLs work
    // and the SameSite=strict cookie is not rejected.
    proxy: {
      '/api': {
        target: process.env.ICARE_API_TARGET ?? 'http://127.0.0.1:8000',
        // Preserve the browser-facing Host: the API checks Origin against it.
        changeOrigin: false,
      },
    },
  },
  build: {
    // Separate outputs for the local app and GitHub Pages preview.
    outDir: mode === 'static' ? 'dist-static' : 'dist',
  },
}))
