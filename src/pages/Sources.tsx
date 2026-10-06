import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Page from '../components/Page'
import { SOURCES } from '../data/sources'

export default function Sources() {
  const { hash } = useLocation()
  // React Router does not scroll to #anchors itself.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'center' })
  }, [hash])
  return (
    <Page title="Sources" subtitle="NASA references used by the prototype.">
      {SOURCES.map((s) => (
        <article key={s.id} id={s.id} className={`panel ${hash === `#${s.id}` ? 'border-accent' : ''}`}>
          <h2 className="font-semibold">{s.title}</h2>
          <p className="label-mono mt-1">{s.organization}</p>
          <p className="text-sm text-ink-300 mt-2"><span className="text-ink-100">Used for:</span> {s.usedFor}</p>
          <a className="text-sm text-accent underline break-all mt-2 inline-block" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
        </article>
      ))}
    </Page>
  )
}
