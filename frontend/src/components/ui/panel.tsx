import { cn } from '@/lib/utils'

/** A bordered surface. Used for primary groupings only — not every list item becomes a card. */
export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <section className={cn('rounded-lg border bg-card', className)} {...props} />
}

export function PanelHeader({ title, description, actions, className }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; className?: string }) {
  return (
    <div className={cn('flex items-start justify-between gap-4 border-b px-5 py-3.5', className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold leading-6">{title}</h2>
        {description && <p className="text-[13px] text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}
