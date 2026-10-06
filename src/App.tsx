import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Header from './components/Header'
import Footer from './components/Footer'
import QuickStart from './components/QuickStart'
import { useApp } from './state/AppState'
import Crew from './pages/Crew'
import Cmo from './pages/Cmo'
import Downlink from './pages/Downlink'
import About from './pages/About'
import Sources from './pages/Sources'

export default function App() {
  const a = useApp()
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
        <Routes>
          <Route path="/" element={<Navigate to="/crew" replace />} />
          <Route path="/crew" element={<Crew />} />
          <Route path="/cmo" element={<Cmo />} />
          <Route path="/downlink" element={<Downlink />} />
          <Route path="/about" element={<About />} />
          <Route path="/sources" element={<Sources />} />
          <Route path="*" element={<Navigate to="/crew" replace />} />
        </Routes>
      </main>
      <Footer />
    </div>
  )
}
