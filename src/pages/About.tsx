import { useEffect, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import Page from '../components/Page'
import { loadBenchmark, type BenchRow } from '../data/benchmark'
import { DEFAULT_SAMPLER } from '../engine/adaptiveSampler'
import { HEALTH_RULES } from '../config/healthRules'

const NAV = [
  ['problem', 'Problem'], ['solution', 'Solution'], ['hazards', 'Hazards addressed'], ['how', 'How it works'],
  ['benchmark', 'Benchmark'], ['limitations', 'Limitations'], ['claims', 'Claims we avoid'], ['future', 'Future work'], ['team', 'Team'],
] as const

export const TEAM: readonly { name: string; role?: string; country: string }[] = [
  { name: 'Syed Hassaan Areeb Kazmi', role: 'Team Owner', country: 'Pakistan' },
  { name: 'Azam Tariq', role: 'Developer', country: 'Pakistan' },
  { name: 'Eman Fatima', role: 'UI/UX Designer', country: 'Pakistan' },
  { name: 'Mohammad Bin Javed', country: 'Pakistan' },
  { name: 'Hudebia', country: 'Pakistan' },
]

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="panel scroll-mt-4" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="text-lg font-semibold">{title}</h2>
      <div className="mt-2 space-y-3 text-sm text-ink-300 leading-relaxed">{children}</div>
    </section>
  )
}

const Ul = ({ children }: { children: ReactNode }) => <ul className="list-disc pl-5 space-y-1.5">{children}</ul>
const B = ({ children }: { children: ReactNode }) => <strong className="text-ink-100">{children}</strong>

const PIPELINE = [
  ['Camera', 'Laptop or tablet camera. Frames stay in the browser.'],
  ['Pose (on-device)', 'MediaPipe lite model, run locally from this app’s own files.'],
  ['Rep metrics', 'Depth, tempo, left/right symmetry and confidence for every rep.'],
  ['Offline logbook', 'Each rep is saved to IndexedDB the moment it completes.'],
  ['Baselines + rules', 'Personal baseline, transparent rules, NOMINAL / WATCH / ACT.'],
  ['Astronaut + CMO views', 'What changed, why it matters, what to do.'],
  ['Downlink queue', 'A compact packet waits for a comms window (simulated).'],
  ['Comms window', 'One-way delay, blackouts and ACKs are simulated.'],
  ['Earth tab', 'A second tab plays the flight surgeon on the ground.'],
] as const

// A real measurement taken while building the app (not a claim about any other device).
const REFERENCE = {
  note: 'Measured 8 Oct 2026 on the development machine, in the desktop app’s built-in browser, on the bundled demo clip, 30 s per mode.',
  full: { mode: 'full', seconds: 30, frames: 371, inferences: 371, avgInferenceMs: 40, reps: 11 } as BenchRow,
  adaptive: { mode: 'adaptive', seconds: 30, frames: 599, inferences: 125, avgInferenceMs: 51, reps: 11 } as BenchRow,
  reductionPct: 79.1,
}

function BenchLine({ label, r }: { label: string; r: BenchRow }) {
  return (
    <tr className="border-t border-space-700">
      <td className="py-1.5 pr-4">{label}</td>
      <td className="pr-4">{r.frames}</td>
      <td className="pr-4">{r.inferences}</td>
      <td className="pr-4">{r.avgInferenceMs.toFixed(0)} ms</td>
      <td>{r.reps}</td>
    </tr>
  )
}

function BenchTable({ full, adaptive }: { full: BenchRow; adaptive: BenchRow }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-sm font-mono text-left">
        <thead className="text-ink-500">
          <tr><th className="pr-4">Mode</th><th className="pr-4">Frames</th><th className="pr-4">Inference calls</th><th className="pr-4">Avg inference</th><th>Reps counted</th></tr>
        </thead>
        <tbody>
          <BenchLine label="Full (every frame)" r={full} />
          <BenchLine label="Adaptive" r={adaptive} />
        </tbody>
      </table>
    </div>
  )
}

export default function About() {
  const { hash } = useLocation()
  const [bench] = useState(loadBenchmark)
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [hash])

  return (
    <Page title="About OrbitFit" subtitle="Exercise-based astronaut health self-monitoring that works offline. A NASA Space Apps Challenge 2026 prototype.">
      <nav aria-label="On this page" className="flex flex-wrap gap-2">
        {NAV.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="text-xs px-2.5 py-1 rounded-md border border-space-600 text-ink-300 hover:bg-space-800">{label}</a>
        ))}
      </nav>

      <Section id="problem" title="The problem">
        <p>
          <B>The challenge</B> (NASA Space Apps 2026): long missions expose astronauts to radiation, isolation and confinement, altered gravity and a closed,
          hostile environment, and on those missions astronauts carry much of the responsibility for spotting changes in themselves. The task is to build health
          monitoring software that gathers health indicators and lets astronauts evaluate and act on the status of their own health. OrbitFit takes on the
          musculoskeletal and behavioural side of that: gravity, isolation and distance (see “Hazards addressed”).
        </p>
        <p>
          In microgravity, muscles and bones are barely loaded, and both decline unless crews exercise hard and regularly. Today that is managed with
          large devices (such as the ARED resistive machine) and constant support from flight surgeons on the ground.
        </p>
        <p>
          On a mission to the Moon or Mars the crew will be far from that support. Messages are delayed, there are communication blackouts, and nobody can
          watch every workout. Astronauts need a simple way to <B>notice early changes in their own musculoskeletal health</B> and act on them,
          without depending on contact with Earth.
        </p>
      </Section>

      <Section id="solution" title="The solution">
        <p>
          OrbitFit turns the exercise astronauts already do into the measurement. A tablet or laptop camera is the only sensor. The app estimates body pose on
          the device, measures every rep (depth, tempo, left/right symmetry), compares it with the person’s <B>own baseline</B>, and answers one question:
          <em> “Is this person deconditioning, and what should they do?”</em>
        </p>
        <Ul>
          <li><B>Astronaut view</B> (<Link className="text-accent underline" to="/crew">/crew</Link>): workout with live feedback, a 30-second daily check-in, and a plain-language status.</li>
          <li><B>Crew Medical Officer view</B> (<Link className="text-accent underline" to="/cmo">/cmo</Link>): every crew member’s trend estimate, alert log and notes.</li>
          <li><B>Earth downlink</B> (<Link className="text-accent underline" to="/downlink">/downlink</Link>): a compact summary the crew can send when a comms window opens.</li>
        </Ul>
        <p>Everything is a static web app. There is no server, no account and no network call at runtime, and it keeps working with the internet switched off.</p>
      </Section>

      <Section id="hazards" title="Hazards addressed">
        <p>
          NASA’s Human Research Program groups the risks of spaceflight into <a className="text-accent underline" href="https://www.nasa.gov/hrp/hazards" target="_blank" rel="noreferrer">five hazards</a>.
          OrbitFit speaks to three of them:
        </p>
        <Ul>
          <li>
            <B>Gravity (and the lack of it).</B> The simulated ARED target load and the rep tempo are scaled to the local gravity (Earth, LEO/ISS, deep-space transit,
            Moon, Mars, or a custom value). Joint angles are computed from 3D landmarks so they do not depend on which way is “up”, which matters when a person floats.
          </li>
          <li>
            <B>Distance from Earth.</B> All analysis runs on the device and is stored locally. The downlink simulates what real distance imposes: a one-way delay
            (5 to 40 minutes), blackouts, queued packets that survive a restart, acknowledgements, retries and duplicate protection.
          </li>
          <li>
            <B>Isolation and confinement.</B> A 30-second daily check-in tracks sleep, fatigue, pain and stress next to the exercise trends. Sustained high stress or poor
            recovery is surfaced for the Crew Medical Officer, and context from the check-in is shown on exercise alerts.
          </li>
        </Ul>
        <p>OrbitFit does <B>not</B> address radiation or closed and hostile environments.</p>
      </Section>

      <Section id="how" title="How it works">
        <ol className="flex flex-wrap gap-2 list-none p-0" aria-label="Data flow">
          {PIPELINE.map(([name, text], i) => (
            <li key={name} className="relative bg-space-900 border border-space-700 rounded-lg p-3 w-44 text-xs">
              <p className="label-mono">{i + 1}</p>
              <p className="font-semibold text-ink-100 text-sm">{name}</p>
              <p className="mt-1">{text}</p>
            </li>
          ))}
        </ol>
        <Ul>
          <li><B>Measurement.</B> Knee, hip and ankle angles come from MediaPipe’s 3D world landmarks. A rep is a top, bottom, top movement with hysteresis; “top” is learned from each person’s own standing angle. A rep with low landmark confidence is rejected with “Measurement unreliable — reposition camera”.</li>
          <li><B>Adaptive sampling.</B> Instead of running the model on every frame, it runs on a base stride and on every frame around the turning points of each rep, which is where depth and tempo are decided.</li>
          <li><B>Baselines.</B> A baseline is the median of a person’s first {HEALTH_RULES.baselineSessions} valid sessions, per exercise. Sessions with too few valid reps or low confidence never count.</li>
          <li><B>Rules.</B> Depth decline, slower lifting, rising left/right asymmetry, rising rep-to-rep variability and exercise adherence, plus check-in rules (pain, recovery, stress) and a combined rule (knee pain with rising asymmetry). Each compares the median of the latest sessions with the baseline, so one bad session cannot raise an alert. All thresholds are in one readable file, <code className="font-mono">src/config/healthRules.ts</code>.</li>
          <li><B>Every alert has three parts:</B> what changed (baseline against now, with a chart), why it matters in spaceflight (with a link to a source), and a suggested action.</li>
        </Ul>
      </Section>

      <section id="benchmark" className="panel scroll-mt-4" aria-labelledby="benchmark-h">
        <h2 id="benchmark-h" className="text-lg font-semibold">Adaptive sampling benchmark</h2>
        <div className="mt-2 space-y-3 text-sm text-ink-300 leading-relaxed">
          <p>
            Adaptive mode runs pose inference on every {DEFAULT_SAMPLER.baseStride}th frame, and on <em>every</em> frame for {DEFAULT_SAMPLER.burstMs} ms after the knee’s angular
            velocity falls towards zero (a turning point). “Calls” are pose-model runs; fewer calls means less battery, heat and CPU on a tablet.
          </p>
          <p className="text-xs">
            Note: the challenge brief says every 5th frame. With the 300 ms turning-point bursts, stride 5 saved 72 to 75% and stride 6 saved 74.5% on the real clip,
            both short of the 75% target, so the base stride is {DEFAULT_SAMPLER.baseStride} (one constant in <code className="font-mono">src/engine/adaptiveSampler.ts</code>).
          </p>

          <div>
            <h3 className="font-semibold text-ink-100">Reference run</h3>
            <p className="text-xs text-ink-500 mb-2">{REFERENCE.note}</p>
            <BenchTable full={REFERENCE.full} adaptive={REFERENCE.adaptive} />
            <p className="mt-2"><span className="text-nominal font-mono">{REFERENCE.reductionPct.toFixed(0)} % fewer inference calls</span> per frame, with the same {REFERENCE.full.reps} reps counted in both modes.</p>
          </div>

          <div>
            <h3 className="font-semibold text-ink-100">Your run on this device</h3>
            {bench ? (
              <div className="mt-1">
                <BenchTable full={bench.full} adaptive={bench.adaptive} />
                <p className="mt-2">
                  <span className="text-nominal font-mono">{bench.reductionPct.toFixed(0)} % fewer inference calls</span> per frame with Adaptive.
                  Source: {bench.source} · {new Date(bench.when).toLocaleString()}
                </p>
              </div>
            ) : (
              <p className="text-ink-500 mt-1">
                None yet. On <Link className="text-accent underline" to="/crew">/crew</Link>, start Demo Mode and press “Run 30 s benchmark” (about a minute: 30 s per mode).
              </p>
            )}
          </div>
        </div>
      </section>

      <Section id="limitations" title="Limitations">
        <Ul>
          <li><B>Prototype, not a medical device.</B> Thresholds are demonstration values. They have not been clinically validated or tested with astronauts.</li>
          <li><B>One camera, kinematic estimates.</B> Accuracy depends on camera placement, lighting and clothing. Pose estimation can be wrong, especially when limbs are hidden.</li>
          <li><B>Camera measurement covers squat and deadlift</B> (knee-angle based). Heel raise has a target load but is not measured by the camera yet.</li>
          <li><B>The ARED load is simulated.</B> The app suggests a target; it does not control or read any hardware. The gravity formulas are a simplified prototype model.</li>
          <li><B>The Earth link is simulated.</B> Packets travel between browser tabs on one device, with a scaled delay (1 simulated minute = 1 second). It is not a radio link.</li>
          <li><B>Demo crew data is synthetic.</B> The 3 crew and 30 days are generated, with one deconditioning, one nominal and one asymmetry-with-pain pattern.</li>
          <li><B>Data lives in this browser.</B> Clearing site data erases it. Export a CSV from the CMO page to keep a copy.</li>
          <li><B>Settling time.</B> The app needs about 1.5 s of standing to learn a person’s top angle, so the very first rep of a set can be missed.</li>
          <li><B>Gravity and form.</B> Movement in real microgravity looks different from the demo footage, and has not been tested.</li>
        </Ul>
      </Section>

      <Section id="claims" title="Claims we avoid">
        <p>OrbitFit is decision support. It uses the words “estimate” and “trend”. It deliberately does not claim:</p>
        <Ul>
          <li><B>No diagnosis.</B> It never says a person has a condition. It says a trend moved and suggests what to check.</li>
          <li><B>No bone density or muscle mass numbers.</B> A camera cannot measure them, so none are shown.</li>
          <li><B>Kinematic estimates only.</B> Everything is derived from body movement seen by a camera: angles, timing, symmetry.</li>
          <li><B>Thresholds are not clinically validated.</B> They are demonstration values, labelled as such wherever they appear.</li>
          <li><B>Device load is simulated.</B> The “ARED target load” is a suggestion from a simplified model, not a reading from a machine.</li>
        </Ul>
      </Section>

      <Section id="future" title="Future work">
        <Ul>
          <li><B>ARED hardware integration:</B> read real load and range of motion from the exercise device instead of simulating it.</li>
          <li><B>Clinical validation:</B> compare the estimates and thresholds against laboratory measurements with researchers and flight surgeons, then set evidence-based thresholds.</li>
          <li><B>Wearable sensor fusion:</B> combine the camera with IMUs and heart-rate sensors for better robustness, including when the camera view is poor.</li>
          <li><B>More movements:</B> heel raise via ankle angle, upper-body lifts, and aerobic exercise.</li>
          <li><B>A real link:</B> replace the simulated tab-to-tab channel with a delay-tolerant transport to a real ground station.</li>
        </Ul>
        <p>See <Link className="text-accent underline" to="/sources">Sources</Link> for the NASA references and credits.</p>
      </Section>

      <Section id="team" title="Team">
        <p>OrbitFit was built for the NASA Space Apps Challenge 2026 by:</p>
        <ul className="grid gap-2 sm:grid-cols-2 list-none p-0" aria-label="Team members">
          {TEAM.map((m) => (
            <li key={m.name} className="bg-space-900 border border-space-700 rounded-lg px-3 py-2">
              <span className="text-ink-100 font-semibold">{m.name}</span>
              {m.role && <span className="block text-xs text-accent">{m.role}</span>}
              <span className="block text-xs text-ink-500">{m.country}</span>
            </li>
          ))}
        </ul>
      </Section>
    </Page>
  )
}
