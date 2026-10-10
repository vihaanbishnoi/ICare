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
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // Output inside frontend/icare-frontend/dist — Person 5 serves this from /
    outDir: 'dist',
  },
})
