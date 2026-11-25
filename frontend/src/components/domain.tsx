import { Badge } from '@/components/ui/badge'
import type { Category, ProviderStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

export function CategoryBadge({ category }: { category: Category | null | undefined }) {
  if (!category) return <Badge variant="outline">Unscored</Badge>
  const v = category === 'HOT' ? 'hot' : category === 'WARM' ? 'warm' : 'cold'
  const label = category === 'HOT' ? 'Hot' : category === 'WARM' ? 'Warm' : 'Cold'
  return <Badge variant={v}>{label}</Badge>
}

const SENT: Record<string, 'ok' | 'hot' | 'warm' | 'accent' | 'default' | 'danger'> = {
  positive: 'ok', interested: 'accent', neutral: 'default', hesitant: 'warm', negative: 'hot', frustrated: 'danger',
}
export function SentimentBadge({ label }: { label: string | null | undefined }) {
  if (!label) return <span className="text-muted-foreground">—</span>
  return <Badge variant={SENT[label] ?? 'default'} className="capitalize">{label}</Badge>
}

export function StatusBadge({ status }: { status: string }) {
  const v = status === 'booked' || status === 'qualified' || status === 'won' ? 'ok' : status === 'cancelled' || status === 'lost' ? 'outline' : 'default'
  return <Badge variant={v} className="capitalize">{status}</Badge>
}

/** Score as a number plus a thin 0-100 track. Colour follows the category, the number carries the value. */
export function ScoreMeter({ score, category, className }: { score: number; category?: Category | null; className?: string }) {
  const c = category === 'HOT' ? 'bg-hot' : category === 'WARM' ? 'bg-warm' : 'bg-cold'
  return (
    <div className={cn('flex items-center gap-2', className)} aria-label={`Lead score ${score} of 100`}>
      <span className="tabular w-7 text-right text-sm font-semibold">{score}</span>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full', c)} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export function ProviderBadge({ provider }: { provider: ProviderStatus | null | undefined }) {
  if (!provider) return null
  if (provider.mode === 'demo')
    return <Badge variant="warm" title="No LLM configured. Answers quote the knowledge base using rule-based templates.">Demo mode (no LLM)</Badge>
  return <Badge variant="live" title="Knowledge answers are written by this model, grounded in retrieved documents.">{provider.active}</Badge>
}

export const unknown = (v: React.ReactNode) => (v === null || v === undefined || v === '' ? <span className="text-muted-foreground">Unknown</span> : v)
