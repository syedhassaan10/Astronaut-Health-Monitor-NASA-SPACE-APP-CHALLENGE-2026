import type { ReactNode } from 'react'

export default function Page({ title, subtitle, children }: { title: string; subtitle?: string; children?: ReactNode }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold">{title}</h1>
      {subtitle && <p className="text-ink-300 mt-1 mb-4">{subtitle}</p>}
      <div className="space-y-4 mt-4">{children}</div>
    </section>
  )
}
