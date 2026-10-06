import type { Level } from '../engine/formFeedback'
import { LM } from '../engine/poseMath'

interface Pt {
  x: number
  y: number
  visibility?: number
}

const BONES: [number, number][] = [
  [LM.L_SHOULDER, LM.R_SHOULDER], [LM.L_SHOULDER, LM.L_HIP], [LM.R_SHOULDER, LM.R_HIP], [LM.L_HIP, LM.R_HIP],
  [LM.L_HIP, LM.L_KNEE], [LM.L_KNEE, LM.L_ANKLE], [LM.R_HIP, LM.R_KNEE], [LM.R_KNEE, LM.R_ANKLE],
  [LM.L_ANKLE, LM.L_FOOT], [LM.R_ANKLE, LM.R_FOOT],
]

export const LEVEL_COLOR: Record<Level | 'neutral', string> = {
  green: '#34d399',
  amber: '#fbbf24',
  red: '#f87171',
  neutral: '#e6edf7',
}

export interface OverlayInfo {
  /** Normalised 2D landmarks of the first person (for drawing only; angles use world landmarks). */
  landmarks: Pt[] | null
  mirror: boolean
  kneeAngle: number | null
  level: Level | 'neutral'
}

/** Draws skeleton + live knee angle. Canvas is sized to the video frame. */
export function drawOverlay(canvas: HTMLCanvasElement, info: OverlayInfo): void {
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const W = canvas.width, H = canvas.height
  ctx.clearRect(0, 0, W, H)
  const lm = info.landmarks
  if (!lm) return
  const px = (i: number): [number, number] | null => {
    const p = lm[i]
    if (!p || (p.visibility ?? 1) < 0.3) return null
    return [(info.mirror ? 1 - p.x : p.x) * W, p.y * H]
  }
  const color = LEVEL_COLOR[info.level]
  ctx.lineWidth = Math.max(2, W / 200)
  ctx.strokeStyle = color
  ctx.fillStyle = color
  for (const [a, b] of BONES) {
    const A = px(a), B = px(b)
    if (!A || !B) continue
    ctx.beginPath()
    ctx.moveTo(A[0], A[1])
    ctx.lineTo(B[0], B[1])
    ctx.stroke()
  }
  for (const i of Object.values(LM)) {
    const P = px(i)
    if (!P) continue
    ctx.beginPath()
    ctx.arc(P[0], P[1], Math.max(3, W / 160), 0, Math.PI * 2)
    ctx.fill()
  }
  if (info.kneeAngle !== null) {
    const K = px(LM.L_KNEE) ?? px(LM.R_KNEE)
    if (K) {
      const size = Math.max(16, W / 28)
      ctx.font = `bold ${size}px ui-monospace, Consolas, monospace`
      const text = `${info.kneeAngle.toFixed(0)}°`
      const x = K[0] + size * 0.6, y = K[1]
      ctx.lineWidth = 4
      ctx.strokeStyle = 'rgba(6,11,22,0.85)'
      ctx.strokeText(text, x, y)
      ctx.fillStyle = color
      ctx.fillText(text, x, y)
    }
  }
}
