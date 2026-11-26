import { Loader2, Mic, Play, Square } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Panel } from '@/components/ui/panel'
import { Empty, ErrorState, Loading } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { api } from '@/lib/api'
import { fmtDateTime } from '@/lib/utils'

function duration(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export default function CallRecordings() {
  const { data, error, loading, reload } = useApi(() => api.recordings(), [])
  const [selected, setSelected] = useState<number | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [loadingId, setLoadingId] = useState<number | null>(null)

  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl) }, [audioUrl])

  const play = async (id: number) => {
    if (selected === id) { setSelected(null); setAudioUrl(null); return }
    setLoadingId(id)
    try {
      const blob = await api.recordingAudio(id)
      setAudioUrl(URL.createObjectURL(blob))
      setSelected(id)
    } catch (e) { toast.error(e instanceof Error ? e.message : 'Could not load recording') }
    finally { setLoadingId(null) }
  }

  return (
    <Panel>
      <div className="border-b px-5 py-4">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold"><Mic className="size-4" />Call recordings</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">Private voice-call audio for manager review. Each caller is notified before recording starts.</p>
      </div>
      {error ? <ErrorState error={error} onRetry={() => reload()} /> : loading && !data ? <Loading label="Loading recordings…" /> : !data?.length ? (
        <Empty icon={Mic} title="No recordings yet" body="Consented voice calls will appear here with the caller name and call time." />
      ) : (
        <ul className="divide-y">
          {data.map((recording) => (
            <li key={recording.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">{recording.customer_name}</p>
                <p className="mt-0.5 text-[12px] text-muted-foreground">{recording.started_at ? fmtDateTime(recording.started_at) : fmtDateTime(recording.created_at)} · {duration(recording.duration_seconds)} · Conversation {recording.conversation_id.slice(0, 8)}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => void play(recording.id)} disabled={loadingId !== null}>
                {loadingId === recording.id ? <Loader2 className="animate-spin" /> : selected === recording.id ? <Square /> : <Play />}
                {loadingId === recording.id ? 'Loading…' : selected === recording.id ? 'Stop' : 'Listen'}
              </Button>
              {selected === recording.id && audioUrl && <audio className="h-9 w-full sm:w-72" controls autoPlay src={audioUrl} aria-label={`Recording of ${recording.customer_name}`} />}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
