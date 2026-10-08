import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Page from '../components/Page'
import { CHALLENGE_DATASETS, CHALLENGE_STATEMENT_SITE, CREDITS, SOURCES } from '../data/sources'

const link = 'text-sm text-accent underline break-all mt-2 inline-block'

export default function Sources() {
  const { hash } = useLocation()
  // React Router does not scroll to #anchors itself.
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'center' })
  }, [hash])
  const hl = (id: string) => (hash === `#${id}` ? 'border-accent' : '')

  return (
    <Page title="Sources" subtitle="What OrbitFit draws on, and what it does not claim.">
      <section aria-labelledby="nasa-h" className="space-y-3">
        <h2 id="nasa-h" className="text-lg font-semibold">NASA references</h2>
        <p className="text-sm text-ink-300">
          Used to explain why the measurements matter and how the demonstration model is shaped. OrbitFit turns these into simplified
          prototype rules; it does not reproduce NASA’s own models or thresholds.
        </p>
        {SOURCES.map((s) => (
          <article key={s.id} id={s.id} className={`panel ${hl(s.id)}`}>
            <h3 className="font-semibold">{s.title}</h3>
            <p className="label-mono mt-1">{s.organization}</p>
            <p className="text-sm text-ink-300 mt-2"><span className="text-ink-100">Used for:</span> {s.usedFor}</p>
            <a className={link} href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
          </article>
        ))}
      </section>

      <section aria-labelledby="credits-h" className="space-y-3 pt-4">
        <h2 id="credits-h" className="text-lg font-semibold">Software and media credits (not NASA)</h2>
        {CREDITS.map((c) => (
          <article key={c.id} id={c.id} className={`panel ${hl(c.id)}`}>
            <h3 className="font-semibold">{c.title}</h3>
            <p className="label-mono mt-1">{c.author}</p>
            <p className="text-sm text-ink-300 mt-2"><span className="text-ink-100">Licence:</span> {c.licence}</p>
            <p className="text-sm text-ink-300 mt-1"><span className="text-ink-100">Used for:</span> {c.usedFor}</p>
            <a className={link} href={c.url} target="_blank" rel="noreferrer">{c.url}</a>
          </article>
        ))}
      </section>

      <section aria-labelledby="datasets-h" className="space-y-3 pt-4">
        <h2 id="datasets-h" className="text-lg font-semibold">Challenge datasets (from the official 2026 challenge statement)</h2>
        <p role="note" className="rounded-md border border-dashed border-watch bg-space-900 px-3 py-2 text-sm text-watch">
          TO FILL: the entries below are placeholders. Copy the dataset names and links from the official statement
          ({' '}<a className="underline" href={CHALLENGE_STATEMENT_SITE} target="_blank" rel="noreferrer">spaceappschallenge.org</a>{' '})
          into <code className="font-mono">CHALLENGE_DATASETS</code> in <code className="font-mono">src/data/sources.ts</code>.
        </p>
        <p className="text-sm text-ink-300">
          Honest status: OrbitFit does <strong className="text-ink-100">not</strong> load any external dataset. The demo crew data is synthetic and generated
          in the app (<code className="font-mono">src/data/demoSeed.ts</code>).
        </p>
        {CHALLENGE_DATASETS.map((d) => (
          <article key={d.id} id={d.id} className="panel border-dashed border-watch/60" aria-label={`Placeholder: ${d.name}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[10px] border border-watch text-watch rounded px-1.5 py-0.5">TO FILL</span>
              <h3 className="font-semibold">{d.name}</h3>
            </div>
            <p className="text-sm text-ink-300 mt-2"><span className="text-ink-100">Used for:</span> {d.usedFor}</p>
            <p className="text-sm text-ink-500 mt-1">Link: <span className="font-mono">{d.url || '[PLACEHOLDER] https://…'}</span></p>
          </article>
        ))}
      </section>
    </Page>
  )
}
