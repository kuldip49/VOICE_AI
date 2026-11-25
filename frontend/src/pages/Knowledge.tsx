import { FileText, Loader2, Search, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Panel, PanelHeader } from '@/components/ui/panel'
import { Empty, ErrorState, Loading } from '@/components/ui/states'
import { useApi } from '@/hooks/useApi'
import { api, type KnowledgeDoc, type SearchResult } from '@/lib/api'
import { cn, fmtDateTime } from '@/lib/utils'

const kb = (n: number) => (n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`)

function ChunksDialog({ doc, onClose }: { doc: KnowledgeDoc; onClose: () => void }) {
  const { data, error, loading } = useApi(() => api.chunks(doc.id), [doc.id])
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent side="right">
        <div className="border-b px-6 py-5 pr-12"><DialogTitle>{doc.filename}</DialogTitle><DialogDescription>{doc.chunk_count} chunks. Each chunk is searched on its own and quoted as a source.</DialogDescription></div>
        <div className="flex-1 space-y-3 overflow-y-auto px-6 py-5">
          {loading ? <Loading /> : error ? <ErrorState error={error} /> : data?.map((c) => (
            <div key={c.id} className="rounded-md border p-3 text-[13px]">
              <div className="mb-1 font-medium">{c.title || `Chunk ${c.index + 1}`}</div>
              <p className="whitespace-pre-line text-muted-foreground">{c.content}</p>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function Knowledge() {
  const docs = useApi(() => api.documents())
  const [uploading, setUploading] = useState(false)
  const [drag, setDrag] = useState(false)
  const [viewing, setViewing] = useState<KnowledgeDoc | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<SearchResult | null>(null)
  const [searching, setSearching] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setUploading(true)
    for (const f of Array.from(files)) {
      try {
        const d = await api.upload(f)
        if (d.status === 'ready') toast.success(`${d.filename}: ${d.chunk_count} chunks indexed`)
        else toast.error(`${d.filename}: ${d.error ?? 'processing failed'}`)
      } catch (e) { toast.error(`${f.name}: ${e instanceof Error ? e.message : 'upload failed'}`) }
    }
    setUploading(false)
    if (fileRef.current) fileRef.current.value = ''
    docs.reload(true)
  }

  const remove = async (id: number) => {
    try { await api.deleteDocument(id); toast.success('Document removed from the knowledge base'); docs.reload(true) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Delete failed') }
    setConfirmId(null)
  }

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setSearching(true)
    try { setResult(await api.search(query.trim(), 3)) } catch (err) { toast.error(err instanceof Error ? err.message : 'Search failed') }
    setSearching(false)
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <Panel>
        <PanelHeader title="Documents" description="The agent answers product and policy questions only from these files." />
        <div className="px-5 pt-4">
          <label
            onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); void upload(e.dataTransfer.files) }}
            className={cn('flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border border-dashed px-4 py-7 text-center hover:bg-muted/50', drag && 'border-primary bg-accent/50')}
          >
            {uploading ? <Loader2 className="size-5 animate-spin text-primary" /> : <Upload className="size-5 text-muted-foreground" />}
            <span className="text-sm font-medium">{uploading ? 'Indexing…' : 'Drop PDF or TXT files, or click to choose'}</span>
            <span className="text-[12px] text-muted-foreground">Up to 5 MB each. Text is extracted, split into sections and indexed for search. Scanned PDFs need OCR first.</span>
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md" multiple className="sr-only" onChange={(e) => upload(e.target.files)} disabled={uploading} />
          </label>
        </div>
        {docs.error ? <ErrorState error={docs.error} onRetry={() => docs.reload()} /> : docs.loading && !docs.data ? <Loading /> : !docs.data?.length ? (
          <Empty icon={FileText} title="Knowledge base is empty" body="Until you add documents the agent will say it cannot answer product questions." />
        ) : (
          <ul className="mt-4 divide-y border-t">
            {docs.data.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-[13px]">
                <FileText className="size-4 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <button className="cursor-pointer truncate font-medium hover:underline" onClick={() => setViewing(d)} disabled={d.status !== 'ready'}>{d.filename}</button>
                  <div className="text-muted-foreground">{kb(d.size_bytes)}, added {fmtDateTime(d.created_at)}{d.error ? `. ${d.error}` : ''}</div>
                </div>
                {d.status === 'ready' ? <Badge variant="ok">{d.chunk_count} chunks</Badge> : d.status === 'failed' ? <Badge variant="danger">Failed</Badge> : <Badge>Processing</Badge>}
                {confirmId === d.id ? (
                  <span className="flex items-center gap-1"><Button size="sm" variant="destructive" onClick={() => remove(d.id)}>Remove</Button><Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>Keep</Button></span>
                ) : <Button size="icon" variant="ghost" aria-label={`Remove ${d.filename}`} onClick={() => setConfirmId(d.id)}><Trash2 /></Button>}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel className="self-start">
        <PanelHeader title="Test retrieval" description="See exactly which passages the agent would use." />
        <form onSubmit={runSearch} className="flex gap-2 px-5 pt-4">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. What is the refund policy?" aria-label="Test question" />
          <Button type="submit" disabled={searching || !query.trim()}>{searching ? <Loader2 className="animate-spin" /> : <Search />} Search</Button>
        </form>
        <div className="space-y-3 px-5 py-4">
          {!result && <p className="text-[13px] text-muted-foreground">Try a question a caller might ask, including one your documents don't cover.</p>}
          {result && (
            <>
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                {result.found ? <Badge variant="ok">Answerable from knowledge base</Badge> : <Badge variant="warm">Not covered: agent will say so</Badge>}
                <span className="text-muted-foreground">Method {result.method}, top score {result.top_score ?? 0} (threshold {result.threshold})</span>
              </div>
              {result.results.map((r, i) => (
                <div key={r.chunk_id} className={cn('rounded-md border p-3 text-[13px]', !result.found && 'opacity-60')}>
                  <div className="flex items-center justify-between gap-2"><span className="font-medium">{i + 1}. {r.title}</span><span className="tabular text-[12px] text-muted-foreground">{r.score.toFixed(2)}</span></div>
                  <div className="text-[12px] text-muted-foreground">{r.document}</div>
                  <p className="mt-1.5 line-clamp-4 whitespace-pre-line">{r.content}</p>
                </div>
              ))}
            </>
          )}
        </div>
      </Panel>
      {viewing && <ChunksDialog doc={viewing} onClose={() => setViewing(null)} />}
    </div>
  )
}
