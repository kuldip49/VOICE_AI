import { CalendarClock, CalendarPlus, Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { StatusBadge } from '@/components/domain'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Empty, ErrorState, Loading } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { api, type Appointment } from '@/lib/api'
import { cn, fmtLocal } from '@/lib/utils'

const dayKey = (iso: string) => iso.slice(0, 10)
const timeOf = (iso: string) => fmtLocal(iso, { weekday: undefined, day: undefined, month: undefined })

function SlotPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const slots = useApi(() => api.slots(), [])
  const byDay = useMemo(() => {
    const m = new Map<string, { start_time: string; label: string }[]>()
    for (const s of slots.data ?? []) m.set(dayKey(s.start_time), [...(m.get(dayKey(s.start_time)) ?? []), s])
    return [...m.entries()]
  }, [slots.data])
  if (slots.loading) return <Loading label="Loading free slots…" className="py-4" />
  if (slots.error) return <ErrorState error={slots.error} className="px-0" />
  if (!byDay.length) return <p className="text-[13px] text-muted-foreground">No free slots in the booking window.</p>
  return (
    <div className="max-h-72 space-y-3 overflow-y-auto pr-1" role="radiogroup" aria-label="Available slots">
      {byDay.map(([day, list]) => (
        <div key={day}>
          <div className="mb-1.5 text-[12px] font-medium text-muted-foreground">{fmtLocal(list[0].start_time, { hour: undefined, minute: undefined })}</div>
          <div className="flex flex-wrap gap-1.5">
            {list.map((s) => (
              <button key={s.start_time} role="radio" aria-checked={value === s.start_time} onClick={() => onChange(s.start_time)}
                className={cn('tabular cursor-pointer rounded-md border px-2.5 py-1 text-[13px] hover:bg-muted', value === s.start_time && 'border-primary bg-accent text-accent-foreground')}>
                {timeOf(s.start_time)}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function BookDialog({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const leads = useApi(() => api.leads({}), [])
  const [customer, setCustomer] = useState('')
  const [slot, setSlot] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    setSaving(true)
    try { await api.book(Number(customer), slot); toast.success('Appointment booked'); onDone(); onClose() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Booking failed') }
    finally { setSaving(false) }
  }
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogTitle>Book a counselling session</DialogTitle>
        <DialogDescription>For a lead who asked to be called back. Slots already taken are hidden.</DialogDescription>
        <div className="mt-4 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="lead">Lead</Label>
            <Select value={customer} onValueChange={setCustomer}>
              <SelectTrigger id="lead"><SelectValue placeholder={leads.loading ? 'Loading…' : leads.data?.length ? 'Choose a lead' : 'No leads yet'} /></SelectTrigger>
              <SelectContent>{leads.data?.map((l) => <SelectItem key={l.id} value={String(l.id)}>{l.name ?? `Caller #${l.id}`}{l.lead.interest ? `, ${l.lead.interest}` : ''}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5"><Label>Time</Label><SlotPicker value={slot} onChange={setSlot} /></div>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={!customer || !slot || saving}>{saving && <Loader2 className="animate-spin" />} Book session</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function RescheduleDialog({ appt, onClose, onDone }: { appt: Appointment; onClose: () => void; onDone: () => void }) {
  const [slot, setSlot] = useState('')
  const [saving, setSaving] = useState(false)
  const submit = async () => {
    setSaving(true)
    try { await api.reschedule(appt.id, slot); toast.success('Appointment moved'); onDone(); onClose() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Could not move the appointment') }
    finally { setSaving(false) }
  }
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogTitle>Move appointment</DialogTitle>
        <DialogDescription>{appt.customer_name ?? 'Caller'} is booked for {fmtLocal(appt.start_time)}.</DialogDescription>
        <div className="mt-4"><SlotPicker value={slot} onChange={setSlot} /></div>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>Keep current time</Button>
          <Button onClick={submit} disabled={!slot || saving}>{saving && <Loader2 className="animate-spin" />} Move appointment</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function Appointments() {
  const { data, error, loading, reload } = useApi(() => api.appointments(false))
  const slots = useApi(() => api.slots(), [])
  const [booking, setBooking] = useState(false)
  const [moving, setMoving] = useState<Appointment | null>(null)
  const [cancelling, setCancelling] = useState<number | null>(null)

  const refresh = () => { reload(true); slots.reload(true) }
  const cancel = async (a: Appointment) => {
    setCancelling(a.id)
    try { await api.cancelAppointment(a.id); toast.success('Appointment cancelled'); refresh() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Cancel failed') }
    finally { setCancelling(null) }
  }

  // next 7 calendar days for the schedule strip
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => {
    const d = new Date(); d.setDate(d.getDate() + i)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  }), [])
  const booked = (data ?? []).filter((a) => a.status === 'booked')
  const freeByDay = useMemo(() => {
    const m: Record<string, number> = {}
    for (const s of slots.data ?? []) m[dayKey(s.start_time)] = (m[dayKey(s.start_time)] ?? 0) + 1
    return m
  }, [slots.data])

  return (
    <div className="space-y-5">
      <Panel>
        <PanelHeader title="Next 7 days" description="Counselling sessions are 30 minutes, online. One counsellor, so a slot can hold one booking."
          actions={<Button onClick={() => setBooking(true)}><CalendarPlus /> Book session</Button>} />
        <div className="grid grid-cols-1 divide-y sm:grid-cols-7 sm:divide-x sm:divide-y-0">
          {days.map((d) => {
            const items = booked.filter((a) => dayKey(a.start_time) === d)
            const [y, m, dd] = d.split('-').map(Number)
            const label = new Date(y, m - 1, dd).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
            return (
              <div key={d} className="min-h-32 px-3 py-3">
                <div className="flex items-baseline justify-between gap-2"><span className="text-[13px] font-semibold">{label}</span><span className="tabular text-[11px] text-muted-foreground">{freeByDay[d] ?? 0} free</span></div>
                <ul className="mt-2 space-y-1.5">
                  {items.map((a) => (
                    <li key={a.id} className="rounded-md border-l-2 border-primary bg-accent/60 px-2 py-1.5 text-[12px]">
                      <div className="tabular font-medium">{timeOf(a.start_time)}</div>
                      <div className="truncate text-muted-foreground">{a.customer_name ?? `Caller #${a.customer_id}`}</div>
                    </li>
                  ))}
                  {!items.length && <li className="text-[12px] text-muted-foreground">{freeByDay[d] ? 'Open' : 'Closed'}</li>}
                </ul>
              </div>
            )
          })}
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="All appointments" />
        {error ? <ErrorState error={error} onRetry={() => reload()} /> : loading && !data ? <Loading /> : !data?.length ? (
          <Empty icon={CalendarClock} title="No appointments yet" body="When a caller confirms a slot with the agent, it is saved here and linked to their lead." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-[13px]">
              <thead className="border-b text-left text-muted-foreground"><tr><th className="px-5 py-2.5 font-medium">When</th><th className="px-3 py-2.5 font-medium">Lead</th><th className="px-3 py-2.5 font-medium">Topic</th><th className="px-3 py-2.5 font-medium">Status</th><th className="px-5 py-2.5 text-right font-medium">Actions</th></tr></thead>
              <tbody className="divide-y">
                {data.map((a) => (
                  <tr key={a.id}>
                    <td className="tabular px-5 py-3 font-medium">{fmtLocal(a.start_time)}</td>
                    <td className="px-3 py-3">{a.customer_name ?? `Caller #${a.customer_id}`}</td>
                    <td className="px-3 py-3 text-muted-foreground">{a.topic}</td>
                    <td className="px-3 py-3"><StatusBadge status={a.status} /></td>
                    <td className="px-5 py-3 text-right">
                      {a.status === 'booked' && new Date(a.start_time) > new Date() ? (
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" onClick={() => setMoving(a)}>Reschedule</Button>
                          <Button size="sm" variant="ghost" className="text-destructive" disabled={cancelling === a.id} onClick={() => cancel(a)}>Cancel</Button>
                        </div>
                      ) : <span className="text-muted-foreground">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {booking && <BookDialog onClose={() => setBooking(false)} onDone={refresh} />}
      {moving && <RescheduleDialog appt={moving} onClose={() => setMoving(null)} onDone={refresh} />}
    </div>
  )
}
