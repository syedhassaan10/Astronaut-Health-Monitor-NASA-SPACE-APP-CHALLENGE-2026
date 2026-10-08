// Verifies that dist/ is complete and consistent. Runs automatically at the end of `npm run build`
// and can be run on its own with `npm run verify`. Exits with an error if anything essential is missing.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const dist = process.argv[2] ?? 'dist'

// Must match normaliseBase() in vite.config.ts.
function normaliseBase(v) {
  const t = (v ?? '').trim()
  if (t === '' || t === '/') return '/'
  return `/${t.replace(/^\/+|\/+$/g, '')}/`
}
const base = normaliseBase(process.env.VITE_BASE)

const errors = []
const warnings = []
const read = (rel) => readFileSync(join(dist, rel), 'utf8')
const size = (rel) => statSync(join(dist, rel)).size
const MB = (n) => (n / 1048576).toFixed(1)

if (!existsSync(dist)) {
  console.error(`verify-dist: "${dist}" does not exist. Run "npm run build" first.`)
  process.exit(1)
}

// 1. Required files (the app must work offline, so the model and WASM must ship inside dist).
const required = [
  ['index.html', 200],
  ['sw.js', 200],
  ['manifest.webmanifest', 50],
  ['icon.svg', 50],
  ['.htaccess', 200],
  ['models/pose_landmarker_lite.task', 1_000_000],
  ['mediapipe/wasm/vision_wasm_internal.js', 10_000],
  ['mediapipe/wasm/vision_wasm_internal.wasm', 1_000_000],
  ['mediapipe/wasm/vision_wasm_module_internal.js', 10_000],
  ['mediapipe/wasm/vision_wasm_module_internal.wasm', 1_000_000],
  ['mediapipe/wasm/vision_wasm_nosimd_internal.js', 10_000],
  ['mediapipe/wasm/vision_wasm_nosimd_internal.wasm', 1_000_000],
]
for (const [rel, min] of required) {
  if (!existsSync(join(dist, rel))) errors.push(`missing ${rel}`)
  else if (size(rel) < min) errors.push(`${rel} is suspiciously small (${size(rel)} bytes)`)
}
if (!existsSync(join(dist, 'demo/squat.mp4'))) {
  warnings.push('demo/squat.mp4 is missing: Demo Mode will be disabled (the "Use video file" option still works).')
}

if (errors.length === 0) {
  // 2. index.html must point at this base path and must not load anything from another host.
  const html = read('index.html')
  if (!html.includes(`${base}assets/`)) errors.push(`index.html does not reference "${base}assets/" (was the build made with the right VITE_BASE?)`)
  if (/(?:src|href)=["']https?:\/\//i.test(html)) errors.push('index.html loads a resource from another host (no CDN allowed)')

  // 3. The web manifest scope/start_url must match the base.
  const manifest = JSON.parse(read('manifest.webmanifest'))
  if (manifest.start_url !== base) errors.push(`manifest start_url is "${manifest.start_url}", expected "${base}"`)
  if (manifest.scope !== base) errors.push(`manifest scope is "${manifest.scope}", expected "${base}"`)

  // 4. The service worker must precache the model and the WASM (that is what makes offline work).
  const sw = read('sw.js')
  for (const f of ['pose_landmarker_lite.task', 'vision_wasm_internal.wasm', 'vision_wasm_nosimd_internal.wasm']) {
    if (!sw.includes(f)) errors.push(`sw.js does not precache ${f}`)
  }

  // 5. .htaccess must contain the rules the host depends on.
  const ht = read('.htaccess')
  const needs = [
    ['application/wasm', 'MIME type for .wasm'],
    ['application/octet-stream', 'MIME type for .task'],
    ['RewriteRule ^ index.html', 'single-page-app fallback'],
    ['https://%{HTTP_HOST}%{REQUEST_URI}', 'HTTPS redirect'],
    ['sw\\.js', 'no-cache rule for sw.js'],
  ]
  for (const [text, why] of needs) if (!ht.includes(text)) errors.push(`.htaccess is missing: ${why}`)
}

// 6. No secrets or environment files in the output.
const walk = (d) => readdirSync(d, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(join(d, e.name)) : [join(d, e.name)]))
const files = walk(dist)
for (const f of files) {
  if (/(^|[\\/])\.env(\.|$)/.test(f)) errors.push(`environment file in dist: ${f}`)
}

const total = files.reduce((n, f) => n + statSync(f).size, 0)
const wasm = files.filter((f) => /\.(wasm|task)$/.test(f)).reduce((n, f) => n + statSync(f).size, 0)

for (const w of warnings) console.warn(`verify-dist: warning: ${w}`)
if (errors.length) {
  console.error(`verify-dist: FAILED (${errors.length} problem${errors.length === 1 ? '' : 's'}):`)
  for (const e of errors) console.error(`  - ${e}`)
  process.exit(1)
}
console.log(`verify-dist: OK. base "${base}", ${files.length} files, ${MB(total)} MB total (${MB(wasm)} MB of model + WASM).`)
