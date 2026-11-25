/* Chart building blocks (Recharts). Colours: validated categorical slots 1-3 from CSS vars;
   one-series charts use a single hue so identity is never colour-only (axis labels carry it). */
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

const axis = { stroke: 'var(--muted-foreground)', fontSize: 12, tickLine: false, axisLine: false } as const

function TooltipBox({ active, payload, label, fmtLabel }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; fmtLabel?: (l: string) => string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border bg-card px-3 py-2 text-[12px] shadow-lg">
      <div className="mb-1 font-medium">{fmtLabel ? fmtLabel(String(label)) : label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="size-2 rounded-full" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="tabular ml-auto pl-3 font-medium">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

const shortDate = (d: string) => new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

export function TrendChart({ data, height = 240 }: { data: { date: string; conversations: number; leads: number; appointments: number }[]; height?: number }) {
  const series = [
    { key: 'conversations', name: 'Conversations', color: 'var(--series-1)' },
    { key: 'leads', name: 'Leads', color: 'var(--series-2)' },
    { key: 'appointments', name: 'Appointments', color: 'var(--series-3)' },
  ]
  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-4 text-[12px] text-muted-foreground" aria-label="Legend">
        {series.map((s) => <li key={s.key} className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded" style={{ background: s.color }} />{s.name}</li>)}
      </ul>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} {...axis} minTickGap={24} />
          <YAxis allowDecimals={false} {...axis} />
          <Tooltip content={<TooltipBox fmtLabel={shortDate} />} cursor={{ stroke: 'var(--input)' }} />
          {series.map((s) => (
            <Line key={s.key} isAnimationActive={false} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2} dot={data.filter((d) => Number(d[s.key as keyof typeof d]) > 0).length <= 2 ? { r: 3, strokeWidth: 0, fill: s.color } : false} activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--card)' }} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Horizontal single-series bar list — labels on the axis, value at the bar end. */
export function BarList({ data, color = 'var(--series-1)', height }: { data: { label: string; value: number }[]; color?: string; height?: number }) {
  const h = height ?? Math.max(120, data.length * 34 + 16)
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ top: 0, right: 28, left: 0, bottom: 0 }} barCategoryGap={8}>
        <XAxis type="number" hide allowDecimals={false} />
        <YAxis type="category" dataKey="label" width={150} {...axis} tick={{ fill: 'var(--foreground)', fontSize: 12 }} />
        <Tooltip content={<TooltipBox />} cursor={{ fill: 'var(--muted)' }} />
        <Bar isAnimationActive={false} dataKey="value" name="Count" fill={color} radius={[0, 4, 4, 0]} maxBarSize={18}
          label={{ position: 'right', fill: 'var(--muted-foreground)', fontSize: 12 }} />
      </BarChart>
    </ResponsiveContainer>
  )
}
