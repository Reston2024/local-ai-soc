import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    proxy: {
      '/health': 'http://localhost:8000',
      '/events': 'http://localhost:8000',
      '/timeline': 'http://localhost:8000',
      '/graph': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/fixtures': 'http://localhost:8000',
    }
  },
  build: {
    outDir: 'dist'
  }
})
