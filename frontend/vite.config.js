import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 900,
    rollupOptions: { output: { manualChunks: { vendor: ['react', 'react-dom', 'react-router-dom'] } } },
  },
})
