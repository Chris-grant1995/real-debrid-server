import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  process.env = {...process.env, ...loadEnv(mode, process.cwd())};
  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': {
          target: process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '/api'), // Keep /api prefix for backend
        },
      },
    },
  };
});
