// Copies MediaPipe WASM runtime from node_modules into /public so it is served
// from our own origin (never a CDN). Runs automatically after `npm install`.
import { cpSync, existsSync, mkdirSync } from 'node:fs'
const src = 'node_modules/@mediapipe/tasks-vision/wasm'
const dst = 'public/mediapipe/wasm'
if (existsSync(src)) {
  mkdirSync(dst, { recursive: true })
  cpSync(src, dst, { recursive: true })
  console.log('[orbitfit] MediaPipe WASM copied to', dst)
} else {
  console.warn('[orbitfit] @mediapipe/tasks-vision not installed; skipping WASM copy')
}
