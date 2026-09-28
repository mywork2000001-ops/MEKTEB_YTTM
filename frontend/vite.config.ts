import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// İnkişaf: /api -> FastAPI (uvicorn --port 8801). İstehsal: FastAPI dist/ qovluğunu özü verir.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8801' } },
  build: { outDir: 'dist', sourcemap: false },
})
