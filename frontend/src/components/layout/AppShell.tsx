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
    <div className="flex items-center gap-3 px-2">
      <span className="brand-mark" aria-hidden>
        <svg viewBox="0 0 40 40" className="size-7" fill="none">
          <path d="M9 26.5c4.8 0 6.2-13 11-13s6.2 13 11 13" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" />
          <path d="M12 30.5h16M15 9.5h10" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity=".62" />
          <circle cx="20" cy="13.5" r="1.5" fill="currentColor" />
        </svg>
      </span>
      <div className="min-w-0 leading-tight">
        <div className="editorial text-[18px] font-semibold tracking-[-.04em]">Kiln &amp; Signal</div>
        <div className="mt-1 text-[9px] font-medium uppercase tracking-[.2em] text-muted-foreground">Client desk</div>
      </div>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="workspace-nav flex flex-col gap-1" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === '/'} onClick={onNavigate}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-[13px] font-medium text-muted-foreground hover:bg-muted/80 hover:text-foreground',
            isActive && 'bg-primary text-primary-foreground shadow-sm hover:bg-primary hover:text-primary-foreground')}>
          <Icon className="size-[17px] opacity-80" strokeWidth={1.7} aria-hidden /> {label}
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
    <div className="min-h-dvh lg:grid lg:grid-cols-[258px_minmax(0,1fr)]">
      <aside className="sidebar-shell sticky top-0 hidden h-dvh flex-col gap-7 border-r bg-sidebar px-4 py-6 lg:flex">
        <Logo />
        <NavItems />
        <div className="mt-auto space-y-3 px-2">
          <div className="border-t pt-4">
            <p className="text-[9px] font-semibold uppercase tracking-[.2em] text-muted-foreground">A thoughtful follow-through</p>
            <p className="mt-2 max-w-[190px] text-[12px] leading-relaxed text-muted-foreground">Keep the important details close, from first hello to next step.</p>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            <span className="size-1.5 rounded-full bg-ok" aria-hidden /> Private workspace
          </div>
        </div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-[278px] flex-col gap-7 border-r bg-sidebar px-4 py-6 shadow-2xl">
            <div className="flex items-center justify-between"><Logo /><Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setOpen(false)}><X /></Button></div>
            <NavItems onNavigate={() => setOpen(false)} />
            <div className="mt-auto border-t px-2 pt-4 text-[12px] leading-relaxed text-muted-foreground">A thoughtful follow-through, from first hello to next step.</div>
          </div>
        </div>
      )}

      <div className="min-w-0">
        <header className="topbar sticky top-0 z-30 flex min-h-[76px] items-center gap-4 border-b px-4 sm:px-7 lg:px-10">
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu /></Button>
          <div className="min-w-0">
            <p className="mb-0.5 text-[9px] font-semibold uppercase tracking-[.2em] text-muted-foreground">Workspace <span className="px-1 opacity-50">/</span> Operations</p>
            <h1 className="editorial truncate text-[21px] font-medium leading-tight tracking-[-.025em]">{title}</h1>
          </div>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            {pub.error ? <span className="text-xs text-destructive">Backend offline</span> : <ProviderBadge provider={pub.data?.provider} />}
            <span className="hidden h-7 w-px bg-border sm:block" aria-hidden />
            <Button variant="ghost" size="icon" className="rounded-full" onClick={toggle} aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}>
              {theme === 'dark' ? <Sun /> : <Moon />}
            </Button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1540px] px-4 py-6 sm:px-7 sm:py-8 lg:px-10">
          <div key={loc.pathname} className="page-stage">
            <Suspense fallback={<Loading />}><Outlet /></Suspense>
          </div>
        </main>
      </div>
    </div>
  )
}
