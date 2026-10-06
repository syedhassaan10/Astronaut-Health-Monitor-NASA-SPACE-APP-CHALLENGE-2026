import type { Status } from '../engine/healthTypes'

const STYLE: Record<Status, { cls: string; icon: string }> = {
  NOMINAL: { cls: 'border-nominal text-nominal', icon: '●' },
  WATCH: { cls: 'border-watch text-watch', icon: '▲' },
  ACT: { cls: 'border-act text-act', icon: '■' },
}

/** Status is conveyed by text AND shape, not by colour alone. */
export default function StatusBadge({ status, large = false }: { status: Status; large?: boolean }) {
  const s = STYLE[status]
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-mono border rounded-md ${s.cls} ${large ? 'px-3 py-1.5 text-base' : 'px-2 py-0.5 text-xs'}`}
      aria-label={`Status ${status}`}
    >
      <span aria-hidden="true">{s.icon}</span>
      {status}
    </span>
  )
}
