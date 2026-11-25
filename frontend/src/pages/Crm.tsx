import { Download, Search, Trash2, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { CategoryBadge, ScoreMeter, SentimentBadge, StatusBadge, unknown } from '@/components/domain'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Panel } from '@/components/ui/panel'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Empty, ErrorState, Loading } from '@/components/ui/states'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useApi } from '@/hooks/useApi'
import { api } from '@/lib/api'
import { fmtDateTime, fmtLocal, inr, relTime } from '@/lib/utils'

const STATUSES = ['new', 'contacted', 'qualified', 'won', 'lost']

function LeadDrawer({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: () => void }) {
  const { data, error, loading, reload } = useApi(() => api.lead(id), [id])
  const [confirmDelete, setConfirmDelete] = useState(false)

  const setStatus = async (status: string) => {
    try { await api.updateLead(id, { status }); toast.success(`Status set to ${status}`); reload(true); onChanged() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Update failed') }
  }
  const forget = async (key?: string) => {
    try { const r = await api.deleteMemories(id, key); toast.success(`Deleted ${r.deleted} saved fact${r.deleted === 1 ? '' : 's'}`); reload(true) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Delete failed') }
  }
  const remove = async () => {
    try { await api.deleteLead(id); toast.success('Lead and all related data deleted'); onChanged(); onClose() }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Delete failed') }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent side="right" aria-describedby={undefined}>
        {loading && !data ? <Loading /> : error ? <ErrorState error={error} onRetry={() => reload()} /> : data && (
          <>
            <div className="border-b px-6 py-5 pr-12">
              <div className="flex flex-wrap items-center gap-2">
                <DialogTitle className="text-lg">{data.name ?? 'Unnamed caller'}</DialogTitle>
                <CategoryBadge category={data.lead.category} />
              </div>
              <DialogDescription className="mt-0.5">Customer #{data.id}, first contact {fmtDateTime(data.created_at)}</DialogDescription>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Select value={data.lead.status} onValueChange={setStatus}>
                  <SelectTrigger className="h-8 w-[150px]" aria-label="Lead status"><SelectValue /></SelectTrigger>
                  <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
                </Select>
                {confirmDelete ? (
                  <span className="flex items-center gap-2 text-[13px]">Delete everything about this customer?
                    <Button size="sm" variant="destructive" onClick={remove}>Delete</Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>Keep</Button>
                  </span>
                ) : <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setConfirmDelete(true)}><Trash2 /> Delete lead</Button>}
              </div>
            </div>
            <Tabs defaultValue="profile" className="flex min-h-0 flex-1 flex-col">
              <TabsList className="px-6"><TabsTrigger value="profile">Profile</TabsTrigger><TabsTrigger value="conversations">Conversations ({data.conversations.length})</TabsTrigger><TabsTrigger value="memory">Saved facts</TabsTrigger></TabsList>
              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                <TabsContent value="profile" className="space-y-6">
                  <dl className="grid grid-cols-[120px_1fr] gap-x-4 gap-y-2 text-[13px]">
                    <dt className="text-muted-foreground">Email</dt><dd>{unknown(data.email)}</dd>
                    <dt className="text-muted-foreground">Phone</dt><dd>{unknown(data.phone)}</dd>
                    <dt className="text-muted-foreground">Interest</dt><dd>{unknown(data.lead.interest)}</dd>
                    <dt className="text-muted-foreground">Budget</dt><dd>{data.lead.budget ? inr(data.lead.budget) : unknown(null)}</dd>
                    <dt className="text-muted-foreground">Timeline</dt><dd>{unknown(data.lead.timeline)}</dd>
                    <dt className="text-muted-foreground">Decision maker</dt><dd>{unknown(data.lead.authority)}</dd>
                    <dt className="text-muted-foreground">Requirements</dt><dd>{unknown(data.lead.requirements)}</dd>
                    <dt className="text-muted-foreground">Purchase intent</dt><dd className="capitalize">{data.lead.intent_level}</dd>
                  </dl>
                  <div>
                    <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Score {data.lead.score}/100</h3><ScoreMeter score={data.lead.score} category={data.lead.category} /></div>
                    <ul className="mt-2 space-y-1 text-[13px] text-muted-foreground">{data.lead.score_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold">Appointments</h3>
                    {data.appointments.length === 0 ? <p className="mt-1 text-[13px] text-muted-foreground">None booked.</p> : (
                      <ul className="mt-2 divide-y rounded-md border text-[13px]">
                        {data.appointments.map((a) => <li key={a.id} className="flex justify-between px-3 py-2"><span>{fmtLocal(a.start_time)}</span><StatusBadge status={a.status} /></li>)}
                      </ul>
                    )}
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold">Sentiment history</h3>
                    {data.sentiments.length === 0 ? <p className="mt-1 text-[13px] text-muted-foreground">No messages analysed yet.</p> : (
                      <ul className="mt-2 space-y-2 text-[13px]">
                        {data.sentiments.slice(0, 6).map((s, i) => <li key={i} className="flex items-start gap-2"><SentimentBadge label={s.label} /><span className="text-muted-foreground">{s.recommended_action}</span></li>)}
                      </ul>
                    )}
                  </div>
                </TabsContent>
                <TabsContent value="conversations" className="space-y-6">
                  {data.conversations.map((c) => (
                    <div key={c.id} className="rounded-md border">
                      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-2.5 text-[13px]">
                        <span className="font-medium">{fmtDateTime(c.started_at)}</span>
                        <Badge variant="outline" className="capitalize">{c.channel}</Badge>
                        <Badge variant="outline">{c.language === 'hi' ? 'Hindi' : 'English'}</Badge>
                        <StatusBadge status={c.status} />
                      </div>
                      {c.summary && (
                        <div className="border-b bg-accent/40 px-4 py-3 text-[13px]">
                          <p>{c.summary.summary}</p>
                          <p className="mt-1.5"><span className="font-medium">Follow-up:</span> {c.summary.follow_up_action}</p>
                          <p className="mt-1 text-[12px] text-muted-foreground">Summary by {c.summary.generated_by}</p>
                        </div>
                      )}
                      <ol className="space-y-2 px-4 py-3 text-[13px]">
                        {c.messages?.map((m) => (
                          <li key={m.id} className="grid grid-cols-[64px_1fr] gap-2">
                            <span className={m.role === 'user' ? 'font-medium' : 'text-muted-foreground'}>{m.role === 'user' ? 'Caller' : 'Agent'}</span>
                            <span className="whitespace-pre-line">{m.content}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ))}
                </TabsContent>
                <TabsContent value="memory">
                  <p className="text-[13px] text-muted-foreground">Facts the agent remembers across conversations. Delete any of them to stop the agent from using it.</p>
                  {data.memories.length === 0 ? <p className="mt-4 text-[13px]">Nothing saved.</p> : (
                    <>
                      <ul className="mt-3 divide-y rounded-md border text-[13px]">
                        {data.memories.map((m) => (
                          <li key={m.key} className="flex items-center gap-3 px-3 py-2">
                            <span className="w-28 shrink-0 capitalize text-muted-foreground">{m.key}</span>
                            <span className="min-w-0 flex-1 truncate">{m.value}</span>
                            <Button size="sm" variant="ghost" onClick={() => forget(m.key)} aria-label={`Forget ${m.key}`}><Trash2 /></Button>
                          </li>
                        ))}
                      </ul>
                      <Button size="sm" variant="outline" className="mt-3" onClick={() => forget()}>Forget all saved facts</Button>
                    </>
                  )}
                </TabsContent>
              </div>
            </Tabs>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default function Crm() {
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [category, setCategory] = useState('all')
  const [status, setStatus] = useState('all')
  const [sort, setSort] = useState('recent')
  const openId = params.get('lead') ? Number(params.get('lead')) : null

  useEffect(() => { const t = setTimeout(() => setDebounced(q), 250); return () => clearTimeout(t) }, [q])
  const { data, error, loading, reload } = useApi(
    () => api.leads({ q: debounced, category: category === 'all' ? '' : category, status: status === 'all' ? '' : status, sort }),
    [debounced, category, status, sort],
  )

  const exportCsv = async () => {
    try {
      const blob = await api.exportCsv()
      const url = URL.createObjectURL(blob)
      const a = Object.assign(document.createElement('a'), { href: url, download: 'kiln-signal-leads.csv' })
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Export failed') }
  }

  const filtered = !!(debounced || category !== 'all' || status !== 'all')

  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2 border-b px-4 py-3 sm:px-5">
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email, phone, course" className="pl-9" aria-label="Search leads" />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-[130px]" aria-label="Filter by category"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All categories</SelectItem><SelectItem value="HOT">Hot</SelectItem><SelectItem value="WARM">Warm</SelectItem><SelectItem value="COLD">Cold</SelectItem></SelectContent>
        </Select>
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="w-[130px]" aria-label="Filter by status"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="all">All statuses</SelectItem>{STATUSES.map((s) => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={sort} onValueChange={setSort}>
          <SelectTrigger className="w-[150px]" aria-label="Sort"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="recent">Recently active</SelectItem><SelectItem value="score">Highest score</SelectItem></SelectContent>
        </Select>
        <Button variant="outline" className="ml-auto" onClick={exportCsv}><Download /> Export CSV</Button>
      </div>

      {error ? <ErrorState error={error} onRetry={() => reload()} /> : loading && !data ? <Loading label="Loading leads…" /> : !data?.length ? (
        filtered ? <Empty icon={Search} title="No leads match these filters" action={<Button size="sm" variant="outline" onClick={() => { setQ(''); setCategory('all'); setStatus('all') }}>Clear filters</Button>} />
          : <Empty icon={Users} title="No leads yet" body="Leads appear here when a caller talks to the agent." action={<Button asChild size="sm"><Link to="/agent">Start a call</Link></Button>} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-[13px]">
            <thead className="border-b text-left text-muted-foreground">
              <tr>
                <th className="px-5 py-2.5 font-medium">Lead</th><th className="px-3 py-2.5 font-medium">Interest</th><th className="px-3 py-2.5 font-medium">Budget</th>
                <th className="px-3 py-2.5 font-medium">Score</th><th className="px-3 py-2.5 font-medium">Sentiment</th><th className="px-3 py-2.5 font-medium">Status</th>
                <th className="px-3 py-2.5 font-medium">Next appointment</th><th className="px-5 py-2.5 text-right font-medium">Last contact</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data.map((l) => (
                <tr key={l.id} className="cursor-pointer hover:bg-muted/50" onClick={() => setParams({ lead: String(l.id) })}>
                  <td className="px-5 py-3">
                    <button className="cursor-pointer text-left font-medium hover:underline" onClick={(e) => { e.stopPropagation(); setParams({ lead: String(l.id) }) }}>{l.name ?? 'Unnamed caller'}</button>
                    <div className="text-muted-foreground">{l.email ?? l.phone ?? 'No contact shared'}</div>
                  </td>
                  <td className="max-w-[220px] truncate px-3 py-3">{unknown(l.lead.interest)}</td>
                  <td className="tabular px-3 py-3">{l.lead.budget ? inr(l.lead.budget) : unknown(null)}</td>
                  <td className="px-3 py-3"><div className="flex items-center gap-2"><ScoreMeter score={l.lead.score} category={l.lead.category} /><CategoryBadge category={l.lead.category} /></div></td>
                  <td className="px-3 py-3"><SentimentBadge label={l.last_sentiment} /></td>
                  <td className="px-3 py-3"><StatusBadge status={l.lead.status} /></td>
                  <td className="px-3 py-3">{l.upcoming_appointment ? fmtLocal(l.upcoming_appointment.start_time) : <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-5 py-3 text-right text-muted-foreground">{relTime(l.last_contact)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {openId && <LeadDrawer id={openId} onClose={() => setParams({})} onChanged={() => reload(true)} />}
    </Panel>
  )
}
