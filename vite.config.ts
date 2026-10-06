import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Base path is configurable for subdomain/subfolder hosting (default "/").
const base = process.env.VITE_BASE ?? '/'

export default defineConfig({
  base,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'OrbitFit',
        short_name: 'OrbitFit',
        description: 'Offline-first exercise-based astronaut health self-monitoring',
        theme_color: '#0b1220',
        background_color: '#0b1220',
        display: 'standalone',
        start_url: base,
        scope: base,
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
        ],
      },
      workbox: {
        // Precache everything, including MediaPipe .wasm and the .task model.
        globPatterns: ['**/*.{js,css,html,svg,png,ico,json,wasm,task,mp4,webm,webmanifest}'],
        maximumFileSizeToCacheInBytes: 40 * 1024 * 1024,
        navigateFallback: 'index.html',
        cleanupOutdatedCaches: true,
      },
    }),
  ],
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
