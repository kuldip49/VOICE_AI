import { BarChart3, BookOpen, CalendarClock, LayoutDashboard, Menu, Moon, PhoneCall, Settings, Sun, Users, X } from 'lucide-react'
import { Suspense, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { ProviderBadge } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Loading } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { useTheme } from '@/hooks/useTheme'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

export const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/agent', label: 'Live agent', icon: PhoneCall },
  { to: '/crm', label: 'Leads', icon: Users },
  { to: '/appointments', label: 'Appointments', icon: CalendarClock },
  { to: '/knowledge', label: 'Knowledge base', icon: BookOpen },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Logo() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
        <rect width="32" height="32" rx="8" className="fill-primary" />
        <path d="M8 18c2.5 0 2.5-6 5-6s2.5 10 5 10 2.5-8 6-8" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
      <div className="leading-tight">
        <div className="text-[15px] font-semibold tracking-tight">SalesPilot</div>
        <div className="text-[11px] text-muted-foreground">TechNova Academy</div>
      </div>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/'} onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground',
            isActive && 'bg-accent text-accent-foreground hover:bg-accent hover:text-accent-foreground')}>
          <Icon className="size-4" aria-hidden /> {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AppShell() {
  const { theme, toggle } = useTheme()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const pub = useApi(() => api.publicSettings(), [loc.pathname === '/settings'])
  const title = NAV.find((n) => (n.to === '/' ? loc.pathname === '/' : loc.pathname.startsWith(n.to)))?.label ?? ''

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 border-r bg-sidebar px-3 py-5 lg:flex">
        <Logo />
        <NavItems />
        <div className="mt-auto space-y-2 px-2 text-[12px] text-muted-foreground">
          <p>Answers come only from your knowledge base.</p>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-64 flex-col gap-6 bg-sidebar px-3 py-5 shadow-xl">
            <div className="flex items-center justify-between"><Logo /><Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setOpen(false)}><X /></Button></div>
            <NavItems onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu /></Button>
          <h1 className="text-[17px] font-semibold tracking-tight">{title}</h1>
          <div className="ml-auto flex items-center gap-2">
            {pub.error ? <span className="text-xs text-destructive">Backend offline</span> : <ProviderBadge provider={pub.data?.provider} />}
            <Button variant="ghost" size="icon" onClick={toggle} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6">
          <Suspense fallback={<Loading />}><Outlet /></Suspense>
        </main>
      </div>
    </div>
  )
}
