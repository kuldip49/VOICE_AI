import { lazy } from 'react'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { useTheme } from '@/hooks/useTheme'

const Overview = lazy(() => import('@/pages/Overview'))
const LiveAgent = lazy(() => import('@/pages/LiveAgent'))
const Crm = lazy(() => import('@/pages/Crm'))
const Appointments = lazy(() => import('@/pages/Appointments'))
const Knowledge = lazy(() => import('@/pages/Knowledge'))
const Analytics = lazy(() => import('@/pages/Analytics'))
const Settings = lazy(() => import('@/pages/Settings'))

function NotFound() {
  return <div className="py-16"><p className="text-sm font-medium">This page doesn't exist.</p><Link to="/" className="text-sm text-primary hover:underline">Go to overview</Link></div>
}

export default function App() {
  const { theme } = useTheme()
  return (
    <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Overview />} />
            <Route path="agent" element={<LiveAgent />} />
            <Route path="crm" element={<Crm />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      <Toaster theme={theme} position="bottom-right" richColors closeButton />
    </BrowserRouter>
  )
}
