import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap', {
  variants: {
    variant: {
      default: 'bg-secondary text-secondary-foreground',
      outline: 'border border-border text-muted-foreground',
      hot: 'bg-hot-soft text-hot',
      warm: 'bg-warm-soft text-warm',
      cold: 'bg-cold-soft text-cold',
      live: 'bg-live-soft text-live',
      ok: 'bg-ok-soft text-ok',
      danger: 'bg-hot-soft text-destructive',
      accent: 'bg-accent text-accent-foreground',
    },
  },
  defaultVariants: { variant: 'default' },
})

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}
