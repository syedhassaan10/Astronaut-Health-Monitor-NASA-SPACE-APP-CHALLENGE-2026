import { lazy, Suspense, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import QuickStart from './components/QuickStart'
import { useApp } from './state/AppState'
import DownlinkSenderHost from './downlink/DownlinkSenderHost'
import AlertLogSync from './state/AlertLogSync'
import { useDbReady } from './state/useDbReady'

// Route-level code splitting keeps the first bundle small; every chunk is still
// precached by the service worker, so nothing here needs the network offline.
const Crew = lazy(() => import('./pages/Crew'))
const Cmo = lazy(() => import('./pages/Cmo'))
const Downlink = lazy(() => import('./pages/Downlink'))
const About = lazy(() => import('./pages/About'))
const Sources = lazy(() => import('./pages/Sources'))

export default function App() {
  const a = useApp()
  const dbState = useDbReady()
  const loc = useLocation()
  // The Earth tab is the receiving end: it must never run the astronaut's sender.
  const isEarthTab = loc.pathname.replace(/\/$/, '').endsWith('/downlink') && new URLSearchParams(loc.search).get('role') === 'earth'
  const [showQS, setShowQS] = useState(!a.quickStartDismissed)
  const close = () => {
    setShowQS(false)
    a.setQuickStartDismissed(true)
  }
  return (
    <div className="min-h-screen flex flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-accent focus:text-space-950 focus:px-3 focus:py-2">
        Skip to content
      </a>
      <Header onQuickStart={() => setShowQS(true)} />
      <main id="main" className="flex-1 mx-auto w-full max-w-7xl px-4 py-6">
        {showQS && <QuickStart onClose={close} />}
        {dbState.status === 'loading' && <p role="status" className="text-ink-500">Opening logbook…</p>}
        {dbState.status === 'error' && (
          <p role="alert" className="panel border-act text-act">
            The offline logbook could not be opened: {dbState.message}. OrbitFit stores its data in this browser&apos;s IndexedDB, so it needs
            storage to be allowed (it does not work in some private windows).
          </p>
        )}
        {dbState.status === 'ready' && (
          <>
          <AlertLogSync />
          {!isEarthTab && <DownlinkSenderHost />}
        <Suspense fallback={<p role="status" className="text-ink-500">Loading…</p>}>
        <Routes>
          <Route path="/" element={<Navigate to="/crew" replace />} />
          <Route path="/crew" element={<Crew />} />
          <Route path="/cmo" element={<Cmo />} />
          <Route path="/downlink" element={<Downlink />} />
          <Route path="/about" element={<About />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="*" element={<Navigate to="/crew" replace />} />
        </Routes>
        </Suspense>
          </>
        )}
      </main>
      <Footer />
    </div>
  )
}
