/// <reference types="node" />
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// The spec's hard constraints, enforced by `npm test`:
//  - static frontend only: no backend, no server-side code, no API keys, no .env secrets
//  - zero runtime network calls to third parties, no CDNs
//  - no China-based APIs, models, SDKs or CDNs
//  - the hosting files exist and contain the rules the host depends on

const read = (p: string) => readFileSync(p, 'utf8')
const SKIP = new Set(['node_modules', 'dist', '.git', 'dist-sub'])

function walk(dir: string, keep: (name: string) => boolean = () => true): string[] {
  return readdirSync(dir).flatMap((name) => {
    if (SKIP.has(name)) return []
    const p = join(dir, name)
    if (statSync(p).isDirectory()) return walk(p, keep)
    return keep(name) ? [p] : []
  })
}

const sourceFiles = walk('src', (n) => /\.(ts|tsx|css)$/.test(n) && !/\.test\.tsx?$/.test(n))

// Vendors/projects headquartered in mainland China, as named in the spec plus other common ones.
const BANNED = /(deepseek|qwen|baidu|alibaba|aliyun|alicdn|tencent|qcloud|bytedance|volcengine|byteimg|zhipu|bigmodel|moonshot|minimax|huawei|sensetime|iflytek|bootcdn|staticfile\.org|cdn\.baomitu|jsdelivr\.net\/gh\/qq)/i

describe('no China-based libraries, APIs or CDNs', () => {
  const pkg = JSON.parse(read('package.json')) as { dependencies?: Record<string, string>; devDependencies?: Record<string, string> }
  const lock = JSON.parse(read('package-lock.json')) as { packages: Record<string, unknown> }

  it('package.json dependencies are clean', () => {
    const names = [...Object.keys(pkg.dependencies ?? {}), ...Object.keys(pkg.devDependencies ?? {})]
    expect(names.filter((n) => BANNED.test(n))).toEqual([])
  })

  it('no installed package (including transitive ones) is from a banned vendor', () => {
    const names = Object.keys(lock.packages).map((k) => k.replace(/^.*node_modules\//, '')).filter(Boolean)
    expect(names.length).toBeGreaterThan(50)
    expect(names.filter((n) => BANNED.test(n))).toEqual([])
  })

  it('no source file or page refers to a banned vendor or CDN', () => {
    const files = [...sourceFiles, 'index.html', 'vite.config.ts', 'package.json']
    const hits = files.filter((f) => BANNED.test(read(f)))
    expect(hits).toEqual([])
  })
})

describe('zero third-party network use at runtime', () => {
  const CDN = /(unpkg\.com|cdn\.jsdelivr|cdnjs\.|googleapis\.com|gstatic\.com|cloudflare\.com\/ajax|bootstrapcdn|esm\.sh|skypack|fonts\.google|use\.typekit|cdn\.tailwindcss|code\.jquery)/i

  it('index.html loads nothing from another host', () => {
    const html = read('index.html')
    expect(html).not.toMatch(/(?:src|href)=["']https?:\/\//i)
    expect(CDN.test(html)).toBe(false)
  })

  it('no source file loads scripts, styles, fonts or data from a CDN', () => {
    expect(sourceFiles.filter((f) => CDN.test(read(f)))).toEqual([])
  })

  it('no source file makes a network request to an absolute http(s) URL', () => {
    const fetchLike = /(fetch|axios\.\w+|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts)\s*\(\s*[`'"]https?:/i
    expect(sourceFiles.filter((f) => fetchLike.test(read(f)))).toEqual([])
    // CSS may not pull remote files either.
    const css = sourceFiles.filter((f) => f.endsWith('.css')).map(read).join('\n')
    expect(css).not.toMatch(/url\(\s*['"]?https?:/i)
  })

  it('every network request in the app targets its own origin (relative or BASE_URL paths)', () => {
    const calls = sourceFiles.flatMap((f) => [...read(f).matchAll(/\bfetch\(\s*([^)]{0,80})\)/g)].map((m) => `${f}: ${m[1]}`))
    for (const c of calls) expect(c).not.toMatch(/https?:\/\//)
  })

  it('MediaPipe is loaded from this app’s own files, not a CDN', () => {
    const loader = read('src/pose/poseLandmarker.ts')
    expect(loader).toContain('mediapipe/wasm')
    expect(loader).toContain('models/pose_landmarker_lite.task')
    expect(loader).not.toMatch(/https?:\/\//)
  })
})

describe('static frontend only: no backend, no secrets', () => {
  it('has no .env files', () => {
    expect(readdirSync('.').filter((n) => /^\.env/.test(n))).toEqual([])
  })

  it('reads exactly one environment variable (the build-time base path)', () => {
    const used = new Set<string>()
    for (const f of [...sourceFiles, 'vite.config.ts']) {
      for (const m of read(f).matchAll(/process\.env\.(\w+)/g)) used.add(m[1]!)
      for (const m of read(f).matchAll(/import\.meta\.env\.(\w+)/g)) used.add(m[1]!)
    }
    expect([...used].sort()).toEqual(['BASE_URL', 'VITE_BASE'])
  })

  it('contains no API keys or tokens', () => {
    const KEY = /(api[_-]?key|secret|access[_-]?token|authorization:\s*bearer|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,})/i
    const files = [...sourceFiles, 'index.html', 'vite.config.ts', 'README.md', 'start.sh', 'start.bat']
    expect(files.filter((f) => KEY.test(read(f)))).toEqual([])
  })

  it('contains no server-side code (no server/api folders, no PHP/Python/Ruby/Go/Java files)', () => {
    const all = walk('.')
    const serverExt = /\.(php|py|rb|go|java|cs|asp|aspx|jsp|pl|cgi|rs)$/i
    expect(all.filter((f) => serverExt.test(f))).toEqual([])
    const dirs = readdirSync('.', { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name)
    expect(dirs.filter((d) => /^(server|api|backend|functions|lambda|cgi-bin)$/i.test(d))).toEqual([])
  })

  it('does not use Node server APIs in app code', () => {
    const NODE = /from ['"](node:)?(http|https|net|child_process|fs|express|koa|fastify)['"]/
    expect(sourceFiles.filter((f) => NODE.test(read(f)))).toEqual([])
  })
})

describe('hosting files', () => {
  const ht = read('public/.htaccess')

  it('.htaccess serves .wasm and .task with the right MIME types', () => {
    expect(ht).toMatch(/AddType\s+application\/wasm\s+\.wasm/)
    expect(ht).toMatch(/AddType\s+application\/octet-stream\s+\.task/)
  })

  it('.htaccess falls back to index.html for deep links, but not for missing files with an extension', () => {
    expect(ht).toMatch(/RewriteCond %\{REQUEST_FILENAME\} !-f/)
    expect(ht).toMatch(/RewriteCond %\{REQUEST_FILENAME\} !-d/)
    expect(ht).toMatch(/RewriteRule \^ index\.html \[L\]/)
    expect(ht).toMatch(/RewriteCond %\{REQUEST_URI\} !\\\.\[A-Za-z0-9\]/)
  })

  it('.htaccess forces HTTPS (also behind a TLS-terminating proxy)', () => {
    expect(ht).toMatch(/RewriteCond %\{HTTPS\} !=on/)
    expect(ht).toMatch(/X-Forwarded-Proto/)
    expect(ht).toMatch(/RewriteRule \^ https:\/\/%\{HTTP_HOST\}%\{REQUEST_URI\} \[L,R=301\]/)
  })

  it('.htaccess caches hashed assets for a year and never caches the entry files', () => {
    expect(ht).toMatch(/max-age=31536000, immutable/)
    expect(ht).toMatch(/index\\\.html\|sw\\\.js\|registerSW\\\.js\|manifest\\\.webmanifest/)
    expect(ht).toMatch(/no-cache/)
  })

  it('every .htaccess block is guarded by <IfModule> so a missing module cannot cause a 500', () => {
    const lines = ht.split('\n').filter((l) => /^\s*(AddType|AddOutputFilterByType|RewriteEngine|RewriteCond|RewriteRule|Header)\b/.test(l))
    let depth = 0
    const unguarded: string[] = []
    for (const raw of ht.split('\n')) {
      const l = raw.trim()
      if (/^<IfModule\b/.test(l)) depth++
      else if (/^<\/IfModule>/.test(l)) depth--
      else if (depth === 0 && lines.includes(raw)) unguarded.push(l)
    }
    expect(unguarded).toEqual([])
  })

  it('vite base path comes from VITE_BASE and defaults to "/"', () => {
    const cfg = read('vite.config.ts')
    expect(cfg).toContain('process.env.VITE_BASE')
    expect(cfg).toMatch(/return '\/'/)
  })

  it('package.json has the dev, build and start scripts (start = vite preview on :4173)', () => {
    const s = (JSON.parse(read('package.json')) as { scripts: Record<string, string> }).scripts
    expect(s.dev).toBeDefined()
    expect(s.build).toContain('vite build')
    expect(s.start).toContain('vite preview')
    expect(s.start).toContain('4173')
  })

  it('start.bat and start.sh serve dist on :4173 in single-page-app mode', () => {
    for (const f of ['start.bat', 'start.sh']) {
      const t = read(f)
      expect(t).toMatch(/serve dist -l .*4173|serve dist -l %PORT%|serve dist -l "\$PORT"/)
      expect(t).toContain(' -s')
    }
    expect(readFileSync('start.bat', 'utf8')).toContain('\r\n') // cmd.exe needs CRLF
    expect(read('start.sh').startsWith('#!')).toBe(true)
  })

  it('is MIT licensed', () => {
    expect(read('LICENSE')).toContain('MIT License')
    expect((JSON.parse(read('package.json')) as { license: string }).license).toBe('MIT')
  })
})

describe('committed build output (local backup works without building)', () => {
  it('dist/ has the app, the pose model, the WASM runtime and .htaccess', () => {
    for (const f of [
      'dist/index.html', 'dist/sw.js', 'dist/.htaccess', 'dist/manifest.webmanifest', 'dist/models/pose_landmarker_lite.task',
      'dist/mediapipe/wasm/vision_wasm_internal.wasm', 'dist/mediapipe/wasm/vision_wasm_nosimd_internal.wasm',
    ]) {
      expect(existsSync(f), f).toBe(true)
    }
  })

  it('dist/ was built for the default base path "/" (so it works at a subdomain root)', () => {
    expect(read('dist/index.html')).toMatch(/(?:src|href)="\/assets\//)
  })
})
