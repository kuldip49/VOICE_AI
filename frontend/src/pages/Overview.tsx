import { ArrowUpRight, CalendarClock, MessagesSquare, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { TrendChart } from '@/components/charts'
import { CategoryBadge, ScoreMeter } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Empty, ErrorState, Skeleton } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { api } from '@/lib/api'
import { fmtLocal, pct, relTime } from '@/lib/utils'

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="min-w-0 px-5 py-4">
      <div className="text-[13px] text-muted-foreground">{label}</div>
      <div className="tabular mt-1 text-[26px] font-semibold leading-none tracking-tight">{value}</div>
      {hint && <div className="mt-1.5 text-[12px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

export default function Overview() {
  const { data, error, loading, reload } = useApi(() => api.overview(14))

  if (error) return <Panel><ErrorState error={error} onRetry={() => reload()} /></Panel>
  if (loading || !data) return (
    <div className="space-y-5"><Skeleton className="h-24" /><div className="grid gap-5 lg:grid-cols-3"><Skeleton className="h-72 lg:col-span-2" /><Skeleton className="h-72" /></div></div>
  )
  const t = data.totals
  const noData = t.engaged_conversations === 0

  return (
    <div className="space-y-6">
      <section className="desk-hero">
        <div className="hero-orbit" aria-hidden>
          <span className="hero-orbit__satellite" />
          <span className="hero-orbit__core">K</span>
        </div>
        <div className="relative z-10 flex min-h-[15.2rem] max-w-[790px] flex-col items-start justify-center px-6 py-7 sm:px-9 sm:py-8">
          <p className="mb-4 flex items-center gap-2 text-[9px] font-medium uppercase tracking-[.22em] text-primary-foreground/65">
            <span className="size-1.5 rounded-full bg-primary-foreground/70" aria-hidden />
            KILN &amp; SIGNAL <span className="opacity-40">/</span> THE DAILY DESK
          </p>
          <h2 className="editorial max-w-[700px] text-[35px] font-normal leading-[1.02] tracking-[-.035em] sm:text-[48px]">
            Keep every <span className="italic">good conversation</span> moving.
          </h2>
          <p className="mt-3 max-w-[470px] text-[13px] leading-relaxed text-primary-foreground/70 sm:text-[14px]">
            A clear view of what your team heard, what each lead needs, and what comes next.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-3">
            <Button asChild className="h-10 rounded-full bg-primary-foreground px-4 text-primary shadow-sm hover:bg-primary-foreground/90">
              <Link to="/agent">Open the conversation desk <ArrowUpRight className="size-4" /></Link>
            </Button>
            <span className="text-[11px] text-primary-foreground/60">
              {noData ? 'Ready for your first conversation' : `${t.engaged_conversations} conversations in the last 14 days`}
            </span>
          </div>
        </div>
      </section>

      <Panel className="grid grid-cols-2 divide-x divide-y sm:grid-cols-3 lg:grid-cols-6 lg:divide-y-0 [&>*]:border-border">
        <Stat label="Conversations" value={t.engaged_conversations} hint={`${t.conversations} session${t.conversations === 1 ? '' : 's'} opened`} />
        <Stat label="Leads" value={t.leads} hint={<span className="flex gap-2"><span className="text-hot">{t.hot} hot</span><span className="text-warm">{t.warm} warm</span><span className="text-cold">{t.cold} cold</span></span>} />
        <Stat label="Avg. lead score" value={t.average_lead_score} hint="out of 100" />
        <Stat label="Appointments" value={t.appointments} hint="booked or completed" />
        <Stat label="Booking rate" value={pct(t.appointment_conversion_rate)} hint="conversations → appointment" />
        <Stat label="Won" value={t.won} hint="leads marked won" />
      </Panel>

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelHeader title="Activity, last 14 days" description="Daily conversations, new leads and booked appointments" />
          <div className="px-3 py-4 sm:px-5">
            <TrendChart data={data.daily} />
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="Upcoming appointments" actions={<Button asChild variant="ghost" size="sm"><Link to="/appointments">View all</Link></Button>} />
          {data.upcoming_appointments.length === 0 ? (
            <Empty icon={CalendarClock} title="Nothing scheduled" body="Appointments booked by the agent or your team show up here." />
          ) : (
            <ul className="divide-y">
              {data.upcoming_appointments.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 px-5 py-3 text-[13px]">
                  <div className="min-w-0"><div className="truncate font-medium">{a.customer_name ?? `Customer #${a.customer_id}`}</div><div className="text-muted-foreground">{a.topic}</div></div>
                  <div className="tabular shrink-0 text-right">{fmtLocal(a.start_time)}</div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel>
          <PanelHeader title="Recent leads" actions={<Button asChild variant="ghost" size="sm"><Link to="/crm">Open CRM</Link></Button>} />
          {data.recent_leads.length === 0 ? <Empty icon={Users} title="No leads yet" body="A lead is created as soon as a caller sends their first message." /> : (
            <ul className="divide-y">
              {data.recent_leads.map((c) => (
                <li key={c.id}>
                  <Link to={`/crm?lead=${c.id}`} className="flex items-center gap-3 px-5 py-3 text-[13px] hover:bg-muted/60">
                    <div className="min-w-0 flex-1"><div className="truncate font-medium">{c.name ?? 'Unnamed caller'}</div><div className="truncate text-muted-foreground">{c.lead.interest ?? 'Interest unknown'}</div></div>
                    <CategoryBadge category={c.lead.category} />
                    <ScoreMeter score={c.lead.score} category={c.lead.category} className="hidden sm:flex" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel>
          <PanelHeader title="Recent conversations" />
          {data.recent_conversations.length === 0 ? <Empty icon={MessagesSquare} title="No conversations yet" /> : (
            <ul className="divide-y">
              {data.recent_conversations.map((c) => (
                <li key={c.id}>
                  <Link to={`/crm?lead=${c.customer_id}`} className="flex items-center gap-3 px-5 py-3 text-[13px] hover:bg-muted/60">
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{c.customer_name ?? 'Unnamed caller'}</div>
                      <div className="truncate text-muted-foreground">{c.summary?.summary ?? `${c.message_count} messages · ${c.channel}`}</div>
                    </div>
                    <span className="shrink-0 text-muted-foreground">{relTime(c.started_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
