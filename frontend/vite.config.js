import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(() => {
  console.log('VITE_BACKEND_PROXY_TARGET:', process.env.VITE_BACKEND_PROXY_TARGET); // Diagnostic print
  return {
    plugins: [react()],
    server: {
      allowedHosts: true,
      proxy: {
        '/api': {
          target: process.env.VITE_BACKEND_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
          // Removed redundant rewrite: (path) => path.replace(/^\/api/, '/api'),
        },
      },
    },
  };
});
