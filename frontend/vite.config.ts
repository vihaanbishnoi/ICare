import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
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
    // Production proxy serves frontend/dist from the same origin as /api/v1.
    outDir: 'dist',
  },
})
