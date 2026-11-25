import { AlertTriangle, BookOpen, Check, ChevronDown, Loader2, Mic, MicOff, PhoneCall, PhoneOff, Send, Square, Volume2, VolumeX, Wrench, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { CategoryBadge, SentimentBadge, unknown } from '@/components/domain'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useApi } from '@/hooks/useApi'
import { voiceSupport, useVoice } from '@/hooks/useVoice'
import { api, type Conversation, type Customer, type Lead, type Message, type Sentiment, type Summary, type ToolCall } from '@/lib/api'
import { cn, fmtLocal, inr } from '@/lib/utils'

type Lang = 'en' | 'hi'
const LOCALE: Record<Lang, string> = { en: 'en-IN', hi: 'hi-IN' }
const CRITERIA: [string, string][] = [['intent', 'Purchase intent'], ['budget_fit', 'Budget fit'], ['urgency', 'Urgency'], ['product_interest', 'Product interest'], ['readiness', 'Readiness']]
const CALL_END_PHRASE = /\b(?:(?:hang|hand)\s*up(?:\s+the)?(?:\s+(?:phone|call))?|end(?:\s+the)?\s+call|finish(?:\s+the)?\s+call|disconnect|goodbye|bye|that'?s all|see you)\b|अलविदा|धन्यवाद,? बस|फोन रख|फोन काट|कॉल (?:खत्म|बंद|समाप्त)|अब बस/i

function isCallEndPhrase(text: string) {
  if (/\b(?:don'?t|do not|never)\s+(?:(?:hang|hand)\s*up|end(?:\s+the)?\s+call|finish(?:\s+the)?\s+call|disconnect|say\s+(?:goodbye|bye))\b/i.test(text)) return false
  return CALL_END_PHRASE.test(text)
}

function generatedLabel(g: string | null) {
  if (!g) return null
  if (g.startsWith('demo-rules (llm-error)')) return { text: 'LLM failed · template answer', tone: 'warm' as const }
  if (g.startsWith('demo-rules')) return { text: 'Template answer (no LLM)', tone: 'outline' as const }
  return { text: `Written by ${g}`, tone: 'live' as const }
}

/** Live level meter: real microphone level while listening, gentle animation while the agent speaks. */
function VoiceMeter({ level, listening, speaking }: { level: number; listening: boolean; speaking: boolean }) {
  const bars = 28
  return (
    <div className="flex h-12 items-center justify-center gap-[3px]" aria-hidden>
      {Array.from({ length: bars }, (_, i) => {
        const shape = 0.35 + 0.65 * Math.sin((i / (bars - 1)) * Math.PI)
        const h = listening ? 4 + level * 40 * shape * (0.6 + ((i * 7) % 5) / 10) : speaking ? 26 * shape : 4
        return (
          <span key={i}
            className={cn('meter-bar w-[3px] rounded-full', listening ? 'bg-live' : speaking ? 'speaking-bar bg-primary' : 'bg-input')}
            style={{ height: `${Math.max(4, h)}px`, animationDelay: speaking ? `${(i % 7) * 0.09}s` : undefined }} />
        )
      })}
    </div>
  )
}

function TraceLine({ calls }: { calls: ToolCall[] }) {
  const [open, setOpen] = useState(false)
  if (!calls.length) return null
  return (
    <div className="mt-2 text-[12px] text-muted-foreground">
      <button onClick={() => setOpen((o) => !o)} className="flex cursor-pointer items-center gap-1.5 hover:text-foreground" aria-expanded={open}>
        <Wrench className="size-3.5" /> {calls.length} agent actions
        <ChevronDown className={cn('size-3.5 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <ol className="mt-1.5 space-y-1 border-l pl-3">
          {calls.map((c, i) => (
            <li key={i} className="flex items-start gap-1.5">
              {c.ok ? <Check className="mt-0.5 size-3.5 shrink-0 text-ok" /> : <X className="mt-0.5 size-3.5 shrink-0 text-destructive" />}
              <span><span className="font-medium text-foreground">{c.tool}</span>{c.detail ? ` — ${c.detail}` : ''}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function Bubble({ m, calls }: { m: Message; calls?: ToolCall[] }) {
  const gen = m.role === 'assistant' ? generatedLabel(m.generated_by) : null
  if (m.role === 'user')
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg rounded-br-sm bg-primary px-3.5 py-2.5 text-[14px] leading-relaxed text-primary-foreground" lang={m.language}>{m.content}</div>
      </div>
    )
  return (
    <div className="max-w-[88%]">
      <div className="whitespace-pre-line rounded-lg rounded-bl-sm border bg-card px-3.5 py-2.5 text-[14px] leading-relaxed" lang={m.language}>{m.content}</div>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {m.sources.map((s) => (
          <Badge key={s.chunk_id} variant="outline" title={s.excerpt}><BookOpen className="size-3" /> {s.document} · {s.title.replace('Course: ', '')}</Badge>
        ))}
        {gen && m.intents.includes('knowledge_question') && <Badge variant={gen.tone}>{gen.text}</Badge>}
      </div>
      {calls && <TraceLine calls={calls} />}
    </div>
  )
}

export default function LiveAgent() {
  const voice = useVoice()
  const pub = useApi(() => api.publicSettings(), [])
  const [lang, setLang] = useState<Lang>('en')
  const [conv, setConv] = useState<Conversation | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [calls, setCalls] = useState<Record<number, ToolCall[]>>({})
  const [lead, setLead] = useState<Lead | null>(null)
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [sentiment, setSentiment] = useState<Sentiment | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [busy, setBusy] = useState<'starting' | 'thinking' | 'ending' | null>(null)
  const [text, setText] = useState('')
  const [muted, setMuted] = useState(false)
  const [handsFree, setHandsFree] = useState(voiceSupport.stt)
  const [offered, setOffered] = useState<string[]>([])
  const activeRef = useRef(false)
  const mutedRef = useRef(muted)
  const handsFreeRef = useRef(handsFree)
  const rateRef = useRef(1)
  // Apply saved voice settings (Settings > Voice): default language, speech rate, read replies aloud.
  const voiceCfg = pub.data?.voice
  useEffect(() => {
    if (!voiceCfg) return
    rateRef.current = voiceCfg.speech_rate || 1
    setMuted(!voiceCfg.auto_speak)
    setLang(voiceCfg.default_language === 'hi-IN' ? 'hi' : 'en')
  }, [voiceCfg])
  useEffect(() => { mutedRef.current = muted; handsFreeRef.current = handsFree }, [muted, handsFree])
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }) }, [messages, busy, voice.interim])

  const say = useCallback(async (content: string, l: string) => {
    if (!mutedRef.current) await voice.speak(content, LOCALE[(l as Lang)] ?? LOCALE.en, rateRef.current)
  }, [voice])

  const finishCall = useCallback(async (id: string) => {
    activeRef.current = false
    voice.abortListening()
    voice.stopSpeaking()
    setBusy('ending')
    try {
      const ended = await api.endConversation(id)
      setConv(ended)
      setSummary(ended.summary)
      toast.success('Call ended. Summary saved to the lead.')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Could not end the call')
    } finally {
      setBusy(null)
    }
  }, [voice])

  const send = useCallback(async (content: string, channel: 'voice' | 'text', convId?: string): Promise<boolean> => {
    const id = convId ?? conv?.id
    if (!id || !content.trim()) return false
    setBusy('thinking')
    const optimistic: Message = { id: -Date.now(), role: 'user', content, language: lang, intents: [], sources: [], generated_by: null, created_at: new Date().toISOString() }
    setMessages((ms) => [...ms, optimistic])
    try {
      const r = await api.sendMessage(id, content, channel)
      setMessages((ms) => [...ms.filter((m) => m.id !== optimistic.id), r.user_message, r.assistant_message])
      setCalls((c) => ({ ...c, [r.assistant_message.id]: r.tool_calls }))
      setLead(r.lead)
      setCustomer(r.customer)
      setSentiment(r.sentiment)
      setOffered(r.conversation.state.offered_slots && !r.conversation.state.pending_slot ? r.conversation.state.offered_slots : [])
      setBusy(null)
      await say(r.assistant_message.content, r.assistant_message.language)
      if (isCallEndPhrase(content)) await finishCall(id)
      return true
    } catch (e) {
      setMessages((ms) => ms.filter((m) => m.id !== optimistic.id))
      setBusy(null)
      toast.error(e instanceof Error ? e.message : 'Message failed')
      return false
    }
  }, [conv?.id, finishCall, lang, say])

  /** Hands-free loop: listen → send → speak → listen again, until the call ends or nothing is heard. */
  const listenLoop = useCallback(async (convId: string) => {
    while (activeRef.current) {
      const heard = await voice.listen(LOCALE[lang])
      if (!activeRef.current || !heard) break
      const ok = await send(heard, 'voice', convId)
      if (!ok || !handsFreeRef.current) break
    }
  }, [lang, send, voice])

  const startCall = async () => {
    setBusy('starting')
    setSummary(null)
    setLead(null); setCustomer(null); setSentiment(null); setCalls({}); setOffered([])
    if (voiceSupport.stt) await voice.requestPermission()
    try {
      const c = await api.startConversation(lang, voiceSupport.stt ? 'voice' : 'text')
      setConv(c)
      setMessages(c.messages ?? [])
      activeRef.current = true
      setBusy(null)
      const greet = c.messages?.[0]
      if (greet) await say(greet.content, lang)
      if (voiceSupport.stt && handsFreeRef.current && activeRef.current) void listenLoop(c.id)
    } catch (e) {
      setBusy(null)
      toast.error(e instanceof Error ? e.message : 'Could not start the conversation')
    }
  }

  const endCall = async () => { if (conv) await finishCall(conv.id) }

  const micClick = async () => {
    if (!conv || conv.status !== 'active') return
    if (voice.listening) { voice.stopListening(); return }
    activeRef.current = true
    void listenLoop(conv.id)
  }

  const submitText = async (e: React.FormEvent) => {
    e.preventDefault()
    const t = text.trim()
    if (!t) return
    setText('')
    voice.abortListening()
    await send(t, 'text')
  }

  const live = conv?.status === 'active'
  const callState = busy === 'starting' ? 'Connecting…' : busy === 'ending' ? 'Ending call…' : voice.listening ? 'Listening' : voice.speaking ? 'Agent speaking' : busy === 'thinking' ? 'Agent is thinking' : live ? 'On call' : conv ? 'Call ended' : 'Ready'
  const weights = pub.data?.lead_scoring_weights ?? { intent: 30, budget_fit: 20, urgency: 20, product_interest: 15, readiness: 15 }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      {/* Call column */}
      <Panel className="flex h-[calc(100dvh-9rem)] min-h-[520px] flex-col overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3 sm:px-5">
          <div className="flex items-center gap-2.5">
            <span className={cn('size-2.5 rounded-full', live ? 'bg-live' : 'bg-input', voice.listening && 'animate-pulse')} aria-hidden />
            <span className="text-sm font-medium" aria-live="polite">{callState}</span>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Select value={lang} onValueChange={(v) => setLang(v as Lang)} disabled={live}>
              <SelectTrigger className="h-8 w-[118px]" aria-label="Conversation language"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="en">English</SelectItem><SelectItem value="hi">हिन्दी (Hindi)</SelectItem></SelectContent>
            </Select>
            {live ? (
              <Button variant="destructive" size="sm" onClick={endCall} disabled={busy === 'ending'}><PhoneOff /> End call</Button>
            ) : (
              <Button variant="live" size="sm" onClick={startCall} disabled={busy === 'starting'}>
                {busy === 'starting' ? <Loader2 className="animate-spin" /> : <PhoneCall />} {conv ? 'New call' : 'Start call'}
              </Button>
            )}
          </div>
        </div>

        {(!voiceSupport.stt || voice.error) && (
          <div className="flex items-start gap-2 border-b bg-warm-soft px-5 py-2.5 text-[13px] text-warm" role="status">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <span>{voice.error ?? 'Voice input is not supported in this browser (use Chrome or Edge). You can still type; replies are read aloud if speech output is available.'}</span>
          </div>
        )}
        {live && lang === 'hi' && voiceSupport.tts && voice.voices.length > 0 && !voice.hasVoiceFor('hi-IN') && (
          <div className="border-b bg-muted px-5 py-2 text-[13px] text-muted-foreground">No Hindi speech voice is installed in this browser, so replies may be read with an English voice. Edge on Windows includes Hindi voices.</div>
        )}

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-5" aria-live="polite" aria-label="Conversation transcript">
          {!conv && (
            <div className="mx-auto max-w-md py-16 text-center">
              <PhoneCall className="mx-auto size-6 text-muted-foreground" />
              <p className="mt-3 text-[15px] font-medium">Talk to Nova like a prospective student would</p>
              <p className="mt-1 text-[13px] text-muted-foreground">Start a call and ask about courses, fees or refunds, share your name and budget, then book a counselling slot. Everything lands in Leads and Appointments.</p>
            </div>
          )}
          {messages.map((m) => <Bubble key={m.id} m={m} calls={calls[m.id]} />)}
          {voice.interim && <div className="flex justify-end"><div className="max-w-[80%] rounded-lg border border-dashed px-3.5 py-2.5 text-[14px] italic text-muted-foreground">{voice.interim}</div></div>}
          {busy === 'thinking' && <div className="flex items-center gap-2 text-[13px] text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Nova is checking the knowledge base…</div>}
          {summary && (
            <div className="rounded-lg border border-primary/30 bg-accent/50 p-4">
              <p className="text-sm font-semibold">Call summary</p>
              <p className="mt-1 text-[13px] leading-relaxed">{summary.summary}</p>
              <p className="mt-2 text-[13px]"><span className="font-medium">Next step:</span> {summary.follow_up_action}</p>
              <Link to="/crm" className="mt-2 inline-block text-[13px] font-medium text-primary hover:underline">Open lead in CRM</Link>
            </div>
          )}
        </div>

        {offered.length > 0 && live && (
          <div className="flex flex-wrap gap-2 border-t px-4 py-2.5 sm:px-5">
            <span className="self-center text-[12px] text-muted-foreground">Pick a slot:</span>
            {offered.map((s, i) => (
              <Button key={s} size="sm" variant="outline" disabled={!!busy} onClick={() => send(String(i + 1), 'text')}>{i + 1}) {fmtLocal(s, { month: undefined, day: 'numeric' })}</Button>
            ))}
          </div>
        )}

        <div className="border-t px-4 py-3 sm:px-5">
          <div className="flex items-center gap-3">
            <Button
              variant={voice.listening ? 'live' : 'outline'} size="icon" className="size-12 shrink-0 rounded-full"
              onClick={micClick} disabled={!live || !voiceSupport.stt || busy === 'thinking'}
              aria-label={voice.listening ? 'Stop listening' : 'Speak'} aria-pressed={voice.listening}
            >
              {voiceSupport.stt ? <Mic className="size-5!" /> : <MicOff className="size-5!" />}
            </Button>
            <div className="hidden min-w-0 flex-1 sm:block"><VoiceMeter level={voice.level} listening={voice.listening} speaking={voice.speaking} /></div>
            <div className="ml-auto flex items-center gap-1">
              {voice.speaking && <Button variant="ghost" size="sm" onClick={voice.stopSpeaking}><Square /> Stop speaking</Button>}
              <Button variant="ghost" size="icon" onClick={() => { setMuted((m) => !m); voice.stopSpeaking() }} aria-label={muted ? 'Unmute agent voice' : 'Mute agent voice'} aria-pressed={muted}>
                {muted ? <VolumeX /> : <Volume2 />}
              </Button>
              {voiceSupport.stt && (
                <label className="ml-1 flex items-center gap-2 text-[12px] text-muted-foreground">
                  <Switch checked={handsFree} onCheckedChange={setHandsFree} aria-label="Hands-free mode" /> Hands-free
                </label>
              )}
            </div>
          </div>
          <form onSubmit={submitText} className="mt-3 flex gap-2">
            <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={live ? (lang === 'hi' ? 'अपना संदेश लिखें…' : 'Type a message…') : 'Start a call to chat'} disabled={!live || busy === 'thinking'} aria-label="Message" maxLength={2000} />
            <Button type="submit" disabled={!live || !text.trim() || busy === 'thinking'} aria-label="Send message"><Send /> <span className="hidden sm:inline">Send</span></Button>
          </form>
        </div>
      </Panel>

      {/* Live lead column */}
      <div className="space-y-5 xl:max-h-[calc(100dvh-9rem)] xl:overflow-y-auto">
        <Panel>
          <PanelHeader title="Caller" description={customer?.id ? `Customer #${customer.id}` : 'Fills in as the caller shares details'} actions={lead && <CategoryBadge category={lead.category} />} />
          <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-2 px-5 py-4 text-[13px]">
            <dt className="text-muted-foreground">Name</dt><dd>{unknown(customer?.name)}</dd>
            <dt className="text-muted-foreground">Interest</dt><dd>{unknown(lead?.interest)}</dd>
            <dt className="text-muted-foreground">Budget</dt><dd>{lead?.budget ? inr(lead.budget) : unknown(null)}</dd>
            <dt className="text-muted-foreground">Timeline</dt><dd>{unknown(lead?.timeline)}</dd>
            <dt className="text-muted-foreground">Needs</dt><dd>{unknown(lead?.requirements)}</dd>
            <dt className="text-muted-foreground">Contact</dt><dd>{unknown(customer?.email || customer?.phone)}</dd>
          </dl>
        </Panel>

        <Panel>
          <PanelHeader title="Lead score" description="Every point has a reason" actions={<span className="tabular text-2xl font-semibold">{lead?.score ?? 0}<span className="text-sm font-normal text-muted-foreground">/100</span></span>} />
          <ul className="space-y-2.5 px-5 py-4">
            {CRITERIA.map(([k, label]) => {
              const got = lead?.score_breakdown?.[k] ?? 0
              const max = weights[k] || 1
              return (
                <li key={k} className="text-[13px]">
                  <div className="flex justify-between"><span>{label}</span><span className="tabular text-muted-foreground">{got}/{max}</span></div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{ width: `${(got / max) * 100}%` }} /></div>
                </li>
              )
            })}
          </ul>
          {lead?.score_reasons?.length ? (
            <details className="border-t px-5 py-3 text-[12px] text-muted-foreground">
              <summary className="cursor-pointer font-medium text-foreground">Why this score</summary>
              <ul className="mt-2 space-y-1">{lead.score_reasons.map((r) => <li key={r}>{r}</li>)}</ul>
            </details>
          ) : null}
        </Panel>

        <Panel>
          <PanelHeader title="Sentiment" description="Latest customer message" actions={<SentimentBadge label={sentiment?.label} />} />
          <div className="space-y-2 px-5 py-4 text-[13px]">
            {sentiment ? (
              <>
                <p className="text-muted-foreground">{sentiment.explanation} <span className="tabular">Confidence {Math.round(sentiment.confidence * 100)}%.</span></p>
                <p><span className="font-medium">Suggested approach:</span> {sentiment.recommended_action}</p>
              </>
            ) : <p className="text-muted-foreground">Appears after the caller's first message.</p>}
          </div>
        </Panel>
      </div>
    </div>
  )
}
