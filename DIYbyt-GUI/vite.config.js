import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Allows external connections
    port: 5173, // Default Vite dev port
  },
  preview: {
    port: 5173,
    host: true,
  }
})