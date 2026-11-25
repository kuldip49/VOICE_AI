import { BarChart3 } from 'lucide-react'
import { useState } from 'react'
import { BarList, TrendChart } from '@/components/charts'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Empty, ErrorState, Skeleton } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { api } from '@/lib/api'
import { pct } from '@/lib/utils'

function ChartPanel({ title, description, rows, empty }: { title: string; description?: string; rows: { label: string; value: number }[]; empty: string }) {
  return (
    <Panel>
      <PanelHeader title={title} description={description} />
      <div className="px-3 py-4 sm:px-5">
        {rows.length ? <BarList data={rows} /> : <p className="px-2 py-6 text-[13px] text-muted-foreground">{empty}</p>}
      </div>
    </Panel>
  )
}

export default function Analytics() {
  const [days, setDays] = useState('14')
  const { data, error, loading, reload } = useApi(() => api.overview(Number(days)), [days])

  if (error) return <Panel><ErrorState error={error} onRetry={() => reload()} /></Panel>
  if (loading && !data) return <div className="grid gap-5 lg:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div>
  if (!data) return null
  const t = data.totals

  if (t.engaged_conversations === 0)
    return <Panel><Empty icon={BarChart3} title="No data to analyse yet" body="Analytics are calculated from stored conversations, leads, sentiment records and appointments. Talk to the agent first." /></Panel>

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <p className="max-w-2xl text-[13px] text-muted-foreground">
          {t.engaged_conversations} conversation{t.engaged_conversations === 1 ? '' : 's'} produced {t.leads} lead{t.leads === 1 ? '' : 's'} ({t.hot} hot, {t.warm} warm, {t.cold} cold) with an average score of {t.average_lead_score}. {pct(t.appointment_conversion_rate)} of conversations ended with a booked counselling session.
        </p>
        <Select value={days} onValueChange={setDays}>
          <SelectTrigger className="w-[140px]" aria-label="Date range"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="7">Last 7 days</SelectItem><SelectItem value="14">Last 14 days</SelectItem><SelectItem value="30">Last 30 days</SelectItem><SelectItem value="90">Last 90 days</SelectItem></SelectContent>
        </Select>
      </div>

      <Panel>
        <PanelHeader title="Conversion trend" description="Conversations, new leads and booked appointments per day" />
        <div className="px-3 py-4 sm:px-5"><TrendChart data={data.daily} height={280} /></div>
      </Panel>

      <div className="grid gap-5 lg:grid-cols-2">
        <ChartPanel title="Lead distribution" description="Hot ≥ 70, warm 40–69, cold < 40" rows={data.lead_distribution.map((d) => ({ label: d.category === 'HOT' ? 'Hot' : d.category === 'WARM' ? 'Warm' : 'Cold', value: d.count }))} empty="No leads yet." />
        <ChartPanel title="Sentiment of customer messages" description="Rule-based classifier, one label per message" rows={data.sentiment_distribution.map((d) => ({ label: d.label[0].toUpperCase() + d.label.slice(1), value: d.count }))} empty="No messages analysed." />
        <ChartPanel title="What callers ask about" description="Questions grouped by topic" rows={data.top_questions.map((d) => ({ label: d.topic, value: d.count }))} empty="No questions recorded." />
        <ChartPanel title="Objections raised" rows={data.top_objections.map((d) => ({ label: d.objection[0].toUpperCase() + d.objection.slice(1), value: d.count }))} empty="No objections detected so far." />
        <ChartPanel title="Courses callers want" rows={data.popular_products.map((d) => ({ label: d.product, value: d.count }))} empty="No course interest captured yet." />
        <ChartPanel title="Conversations per week" rows={data.weekly.map((d) => ({ label: d.week, value: d.conversations }))} empty="No weekly data." />
      </div>
    </div>
  )
}
