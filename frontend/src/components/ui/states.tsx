import { AlertTriangle, Loader2 } from 'lucide-react'
import { Button } from './button'
import { cn } from '@/lib/utils'

export function Loading({ label = 'Loading…', className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={cn('flex items-center gap-2 px-5 py-10 text-sm text-muted-foreground', className)}>
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-muted', className)} />
}

export function Empty({ icon: Icon, title, body, action, className }: { icon: React.ElementType; title: string; body?: string; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex flex-col items-start gap-2 px-5 py-10', className)}>
      <Icon className="size-5 text-muted-foreground" aria-hidden />
      <p className="text-sm font-medium">{title}</p>
      {body && <p className="max-w-md text-[13px] text-muted-foreground">{body}</p>}
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export function ErrorState({ error, onRetry, className }: { error: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={cn('flex flex-col items-start gap-2 px-5 py-8', className)}>
      <div className="flex items-center gap-2 text-sm font-medium text-destructive"><AlertTriangle className="size-4" /> Couldn't load this data</div>
      <p className="max-w-md text-[13px] text-muted-foreground">{error}</p>
      {onRetry && <Button size="sm" variant="outline" onClick={onRetry}>Try again</Button>}
    </div>
  )
}
