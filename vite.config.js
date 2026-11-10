import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import process from 'node:process'

export default defineConfig({
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000', '/simular': 'http://127.0.0.1:8000', '/salud': 'http://127.0.0.1:8000' },
    watch: { ignored: ['**/backend/.postgres/**','**/backend/backups/**','**/backend/.venv/**','**/backend/migration-reports/**'] },
    fs: { deny: ['**/.env','**/.env.*','**/*.{crt,pem}','**/.git/**','**/backend/**'] },
  },
  optimizeDeps: { entries: ['index.html'] },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(process.cwd(), './src'),
    },
  },
})
