import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/usretail/',
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 1200,
  },
})
