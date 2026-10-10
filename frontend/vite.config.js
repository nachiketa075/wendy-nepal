import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API is reached through this proxy so the browser sees one origin and the
// owner session cookie stays same-site in development.
const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: false, xfwd: true } },
  },
})
