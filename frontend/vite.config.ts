import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => {
  const proxy = {
      '/api': {
        target: loadEnv(mode, '.', 'FCC_').FCC_TEST_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
  }

  return {
    plugins: [react(), tailwindcss()],
    server: { host: '0.0.0.0', proxy },
    preview: { proxy },
    test: {
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      setupFiles: './src/test/setup.ts',
    },
  }
})
