import { CheckCircle2, CircleAlert, KeyRound, Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input, Textarea } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ErrorState, Loading } from '@/components/ui/states'
import { Switch } from '@/components/ui/switch'
import { useApi } from '@/hooks/useApi'
import { adminKey, api, type SettingsBundle } from '@/lib/api'

type S = SettingsBundle['settings']
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const CRITERIA: [string, string][] = [['intent', 'Purchase intent'], ['budget_fit', 'Budget fit'], ['urgency', 'Urgency'], ['product_interest', 'Product interest'], ['readiness', 'Readiness']]

function Row({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="grid gap-1.5 py-3 sm:grid-cols-[200px_1fr] sm:gap-6">
      <div><Label>{label}</Label>{hint && <p className="mt-0.5 text-[12px] text-muted-foreground">{hint}</p>}</div>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

function Status({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return <span className="flex items-center gap-1.5">{ok ? <CheckCircle2 className="size-4 text-ok" /> : <CircleAlert className="size-4 text-warm" />}{children}</span>
}

function useSection<K extends keyof S>(key: K, initial: S[K] | undefined) {
  const [value, setValue] = useState<S[K] | undefined>(initial)
  const [saving, setSaving] = useState(false)
  useEffect(() => setValue(initial), [initial])
  const save = async () => {
    if (!value) return
    setSaving(true)
    try { setValue(await api.saveSettings(key, value)); toast.success('Settings saved') }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Save failed') }
    finally { setSaving(false) }
  }
  return { value, setValue, saving, save }
}

function SaveBar({ saving, onSave, disabled }: { saving: boolean; onSave: () => void; disabled?: boolean }) {
  return <div className="flex justify-end border-t px-5 py-3"><Button onClick={onSave} disabled={saving || disabled}>{saving && <Loader2 className="animate-spin" />} Save changes</Button></div>
}

export default function Settings() {
  const { data, error, loading, reload } = useApi(() => api.settings())
  const [key, setKey] = useState(adminKey.get())
  const biz = useSection('business_profile', data?.settings.business_profile)
  const agent = useSection('agent_instructions', data?.settings.agent_instructions)
  const sched = useSection('scheduling', data?.settings.scheduling)
  const scoring = useSection('lead_scoring', data?.settings.lead_scoring)
  const voice = useSection('voice', data?.settings.voice)

  const access = (
    <Panel>
      <PanelHeader title="Access" description="Needed only when the server sets ADMIN_API_KEY. Stored in this browser, sent as a request header." />
      <div className="flex flex-wrap items-center gap-2 px-5 py-4">
        <KeyRound className="size-4 text-muted-foreground" />
        <Input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Admin key" className="max-w-xs" aria-label="Admin key" autoComplete="off" />
        <Button variant="outline" onClick={() => { adminKey.set(key.trim()); toast.success(key ? 'Admin key saved in this browser' : 'Admin key cleared'); reload() }}>Save key</Button>
      </div>
    </Panel>
  )

  if (error) return <div className="space-y-5">{access}<Panel><ErrorState error={error} onRetry={() => reload()} /></Panel></div>
  if (loading || !data) return <Loading />
  const env = data.environment
  const weightSum = scoring.value ? Object.values(scoring.value.weights).reduce((a, b) => a + (Number(b) || 0), 0) : 100

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="space-y-5">
        <Panel>
          <PanelHeader title="Business profile" description="Change these and the knowledge base to run the agent for another business." />
          {biz.value && (
            <div className="divide-y px-5">
              <Row label="Company name"><Input value={biz.value.company_name} onChange={(e) => biz.setValue({ ...biz.value!, company_name: e.target.value })} /></Row>
              <Row label="Agent name" hint="Used in greetings"><Input value={biz.value.agent_name} onChange={(e) => biz.setValue({ ...biz.value!, agent_name: e.target.value })} /></Row>
              <Row label="Description"><Textarea value={biz.value.description} onChange={(e) => biz.setValue({ ...biz.value!, description: e.target.value })} /></Row>
              <Row label="Contact email"><Input value={biz.value.contact_email} onChange={(e) => biz.setValue({ ...biz.value!, contact_email: e.target.value })} /></Row>
              <Row label="Contact phone" hint="Business contact details only; inbound call routing is configured below."><Input value={biz.value.contact_phone} onChange={(e) => biz.setValue({ ...biz.value!, contact_phone: e.target.value })} /></Row>
              <Row label="Products" hint="Recognised from these keywords">
                <ul className="space-y-1 text-[13px]">{Object.entries(biz.value.products).map(([p, kws]) => <li key={p}><span className="font-medium">{p}</span> <span className="text-muted-foreground">{kws.slice(0, 5).join(', ')}</span></li>)}</ul>
              </Row>
            </div>
          )}
          <SaveBar saving={biz.saving} onSave={biz.save} />
        </Panel>

        <Panel>
          <PanelHeader title="Agent instructions" description="System prompt for the LLM. Ignored in demo mode, where answers are templates." />
          {agent.value && <div className="px-5 py-4"><Textarea rows={7} value={agent.value.system_prompt} onChange={(e) => agent.setValue({ system_prompt: e.target.value })} aria-label="System prompt" /></div>}
          <SaveBar saving={agent.saving} onSave={agent.save} />
        </Panel>

        <Panel>
          <PanelHeader title="Lead scoring" description="Points available per criterion. Must add up to 100." />
          {scoring.value && (
            <div className="divide-y px-5">
              {CRITERIA.map(([k, label]) => (
                <Row key={k} label={label}>
                  <Input type="number" min={0} max={100} className="w-28" value={scoring.value!.weights[k]}
                    onChange={(e) => scoring.setValue({ ...scoring.value!, weights: { ...scoring.value!.weights, [k]: Number(e.target.value) } })} />
                </Row>
              ))}
              <Row label="Thresholds" hint="Hot at or above, warm at or above">
                <div className="flex items-center gap-2 text-[13px]">
                  Hot <Input type="number" className="w-20" value={scoring.value.hot_threshold} onChange={(e) => scoring.setValue({ ...scoring.value!, hot_threshold: Number(e.target.value) })} />
                  Warm <Input type="number" className="w-20" value={scoring.value.warm_threshold} onChange={(e) => scoring.setValue({ ...scoring.value!, warm_threshold: Number(e.target.value) })} />
                </div>
              </Row>
              <p className={`py-2 text-[13px] ${weightSum === 100 ? 'text-muted-foreground' : 'text-destructive'}`}>Total {weightSum}/100{weightSum !== 100 && ', adjust before saving'}</p>
            </div>
          )}
          <SaveBar saving={scoring.saving} onSave={scoring.save} disabled={weightSum !== 100} />
        </Panel>

        <Panel>
          <PanelHeader title="Appointment availability" />
          {sched.value && (
            <div className="divide-y px-5">
              <Row label="Working days">
                <div className="flex flex-wrap gap-1.5">
                  {DAYS.map((d, i) => {
                    const on = sched.value!.working_days.includes(i)
                    return <Button key={d} size="sm" variant={on ? 'default' : 'outline'} aria-pressed={on}
                      onClick={() => sched.setValue({ ...sched.value!, working_days: on ? sched.value!.working_days.filter((x) => x !== i) : [...sched.value!.working_days, i].sort() })}>{d}</Button>
                  })}
                </div>
              </Row>
              <Row label="Hours"><div className="flex items-center gap-2 text-[13px]">From <Input type="number" min={0} max={23} className="w-20" value={sched.value.start_hour} onChange={(e) => sched.setValue({ ...sched.value!, start_hour: Number(e.target.value) })} /> to <Input type="number" min={1} max={24} className="w-20" value={sched.value.end_hour} onChange={(e) => sched.setValue({ ...sched.value!, end_hour: Number(e.target.value) })} /></div></Row>
              <Row label="Slot length">
                <Select value={String(sched.value.slot_minutes)} onValueChange={(v) => sched.setValue({ ...sched.value!, slot_minutes: Number(v) })}>
                  <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
                  <SelectContent>{[15, 20, 30, 45, 60].map((m) => <SelectItem key={m} value={String(m)}>{m} minutes</SelectItem>)}</SelectContent>
                </Select>
              </Row>
              <Row label="Booking window" hint="Days ahead the agent can offer"><Input type="number" min={1} max={60} className="w-24" value={sched.value.days_ahead} onChange={(e) => sched.setValue({ ...sched.value!, days_ahead: Number(e.target.value) })} /></Row>
            </div>
          )}
          <SaveBar saving={sched.saving} onSave={sched.save} />
        </Panel>

        <Panel>
          <PanelHeader title="Voice" />
          {voice.value && (
            <div className="divide-y px-5">
              <Row label="Default language">
                <Select value={voice.value.default_language} onValueChange={(v) => voice.setValue({ ...voice.value!, default_language: v })}>
                  <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectItem value="en-IN">English (India)</SelectItem><SelectItem value="hi-IN">Hindi (India)</SelectItem></SelectContent>
                </Select>
              </Row>
              <Row label="Speech rate"><Input type="number" step={0.1} min={0.5} max={1.5} className="w-24" value={voice.value.speech_rate} onChange={(e) => voice.setValue({ ...voice.value!, speech_rate: Number(e.target.value) })} /></Row>
              <Row label="Read replies aloud"><Switch checked={voice.value.auto_speak} onCheckedChange={(c) => voice.setValue({ ...voice.value!, auto_speak: c })} /></Row>
            </div>
          )}
          <SaveBar saving={voice.saving} onSave={voice.save} />
        </Panel>
      </div>

      <div className="space-y-5">
        <Panel>
          <PanelHeader title="Environment" description="Read from the server. Secrets are never shown." />
          <ul className="space-y-2.5 px-5 py-4 text-[13px]">
            <li><Status ok={env.provider.mode === 'llm'}>AI model: {env.provider.mode === 'llm' ? env.provider.active : 'none, demo mode (template answers)'}</Status></li>
            <li><Status ok={env.provider.grok_key_present}>Grok API key {env.provider.grok_key_present ? 'configured' : 'not set'}</Status></li>
            <li><Status ok={env.provider.gemini_key_present}>Gemini API key {env.provider.gemini_key_present ? 'configured' : 'not set'}</Status></li>
            <li className="pl-6 text-muted-foreground">Ollama: {env.provider.ollama_model} at {env.provider.ollama_url}</li>
            <li><Status ok={env.chunks_with_embeddings > 0}>Retrieval: {env.chunks_with_embeddings > 0 ? 'hybrid keyword + embeddings' : 'BM25 keyword search (no embeddings)'}</Status></li>
            <li><Status ok>Database: {env.database}</Status></li>
            <li><Status ok>Calendar: {env.calendar_provider}</Status></li>
            <li><Status ok={env.admin_auth_enabled}>Admin key {env.admin_auth_enabled ? 'required' : 'not required (local development)'}</Status></li>
            <li className="pl-6 text-muted-foreground">Uploads up to {env.max_upload_mb} MB, chat rate limit {env.rate_limit_per_minute}/min per IP, timezone {env.timezone}</li>
          </ul>
          <div className="border-t px-5 py-3 text-[12px] text-muted-foreground">
            Change these in <code className="rounded bg-muted px-1">backend/.env</code> and restart the backend. <Badge variant="outline" className="ml-1">{env.environment}</Badge>
          </div>
        </Panel>
        {env.telephony.ready && <Panel>
          <PanelHeader title="Inbound phone" description="Exotel AgentStream carries phone audio to this API; Sarvam handles live speech recognition and speech output." />
          <ul className="space-y-2.5 px-5 py-4 text-[13px]">
            <li><Status ok={env.telephony.account_configured}>Exotel account key and token {env.telephony.account_configured ? 'configured' : 'missing from backend/.env'}</Status></li>
            <li><Status ok={Boolean(env.telephony.phone_number)}>ExoPhone {env.telephony.phone_number || 'not set in backend/.env'}</Status></li>
            <li><Status ok={env.telephony.stream_configured}>Public WSS endpoint {env.telephony.stream_configured ? env.telephony.wss_url : 'missing EXOTEL_PUBLIC_WSS_URL'}</Status></li>
            <li><Status ok={env.telephony.speech_configured}>Sarvam speech API key {env.telephony.speech_configured ? 'configured' : 'missing SARVAM_API_KEY'}</Status></li>
            <li><Status ok={env.telephony.ready}>Environment fields {env.telephony.ready ? 'complete; Exotel flow assignment still required' : 'incomplete'}</Status></li>
          </ul>
          <div className="border-t px-5 py-3 text-[12px] text-muted-foreground">
            Run <code className="rounded bg-muted px-1">python -m app.telephony_setup</code> to print the WSS endpoint and Exotel setup steps. In Exotel, assign the number to an App Bazaar flow with a Voicebot applet. Details: <code className="rounded bg-muted px-1">docs/TELEPHONY_SETUP.md</code>.
          </div>
        </Panel>}
        {access}
      </div>
    </div>
  )
}
