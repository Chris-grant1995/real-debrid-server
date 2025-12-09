import { defineConfig } from 'vite' // No need for loadEnv
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({ // No need for ({ mode }) => { and process.env = ...
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000', // Use process.env directly
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
      },
    },
  },
});
