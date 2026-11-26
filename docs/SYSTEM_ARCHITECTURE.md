# System architecture

Sources: `docs/diagrams/*.mmd` (Mermaid). Editable draw.io versions: [diagrams/DRAWIO_LINKS.md](diagrams/DRAWIO_LINKS.md).

## Implemented MVP

```mermaid
flowchart LR
  subgraph Browser["Browser (Chrome / Edge)"]
    UI["React + TypeScript dashboard"]
    STT["Web Speech API: SpeechRecognition"]
    TTS["speechSynthesis"]
  end
  subgraph Backend["FastAPI backend"]
    API["REST API /api/*"]
    STREAM["Exotel AgentStream WSS bridge"]
    AGENT["Agent orchestrator"]
    TOOLS["10 validated tools + logs"]
    RAG["RAG: chunks + BM25 (+embeddings)"]
    SCORE["Scoring, sentiment, extraction, summaries"]
    CAL["Local calendar"]
  end
  DB[("SQLite, 13 tables")]
  LLM["Gemini / Ollama (optional)"]
  EXO["Exotel ExoPhone + Voicebot flow"]
  SARVAM["Sarvam realtime STT / TTS"]
  UI <--> STT
  UI <--> TTS
  UI -- "JSON over HTTP (Vite proxy)" --> API --> AGENT --> TOOLS
  TOOLS --> RAG --> DB
  TOOLS --> SCORE --> DB
  TOOLS --> CAL --> DB
  AGENT -. "grounded prompt" .-> LLM
  EXO <-->|"16 kHz PCM audio over authenticated WSS"| STREAM
  STREAM <--> SARVAM
  STREAM -->|"final transcript"| AGENT
```

## Layers

### Frontend (`frontend/`)
- **React 19 + TypeScript + Vite**. Pages are lazy-loaded routes: Overview, Live agent, Leads (CRM), Appointments, Knowledge base, Analytics, Settings.
- **Tailwind CSS v4** with design tokens in `src/index.css` (light + dark), **shadcn/ui-pattern components** in `src/components/ui` (Radix primitives + class-variance-authority), **Lucide** icons, **Recharts** charts, **sonner** toasts.
- `src/lib/api.ts`: typed API client. All calls go to `/api`, which the Vite dev server proxies to `127.0.0.1:8000`, so the browser never needs the backend URL or any secret.
- `src/hooks/useVoice.ts`: STT, TTS, microphone level meter, error mapping, barge-in.

### Voice pipeline
1. `SpeechRecognition` (lang `en-IN` or `hi-IN`) produces interim + final text. In Chrome the audio is sent to Google's speech service, so it needs internet; nothing is stored by Kiln & Signal.
2. Final text is POSTed to `/api/conversations/{id}/messages` with `channel=voice`.
3. The reply is read with `speechSynthesis` using a voice that matches the reply language.
4. Hands-free mode loops listen → send → speak. Clicking the mic while the agent speaks cancels speech (barge-in).
5. Unsupported browser / blocked mic / no speech / network errors show a clear banner and the text box keeps working.

### Inbound telephone pipeline
1. The ExoPhone is assigned to an Exotel App Bazaar flow containing a Voicebot applet.
2. The applet opens the authenticated `/api/telephony/exotel/stream` WSS endpoint. In Docker, Nginx forwards the WebSocket upgrade to FastAPI; the Vite dev proxy also permits WebSockets.
3. The bridge forwards 16 kHz mono linear16 caller audio to Sarvam realtime STT. Final transcripts enter the same SalesAgent and CRM workflow used by browser conversations.
4. Sarvam TTS produces linear16 audio that the bridge streams back to Exotel for playback. Pressing 9 switches English/Hindi; a goodbye closes the conversation and records a summary.
5. This path is implemented in code, but a live call still needs Exotel AgentStream enablement, a number-to-flow assignment, public WSS hosting, Exotel credentials and a Sarvam key. Provider usage may be charged.

### Backend (`backend/app/`)
| File | Responsibility |
|---|---|
| `main.py` | App, CORS, generic 500 handler, startup (create tables, seed KB) |
| `config.py` | Settings from environment / `.env` |
| `models.py` | 13 SQLAlchemy tables |
| `agent/orchestrator.py` | Per-message pipeline: language → extraction → sentiment → intent planner → tools → scoring → reply |
| `agent/tools.py` | The 10 tools, Pydantic input schemas, permission list, execution log |
| `services/rag.py` | Text extraction, chunking, BM25 index, optional embeddings, not-found guard |
| `services/llm.py` | Provider abstraction: Gemini (REST), Ollama (local), demo |
| `services/exotel_stream.py` | Exotel/Sarvam streaming audio bridge for inbound phone calls |
| `routers/telephony.py` | Exotel Basic Auth WebSocket endpoint and shared CRM callbacks |
| `services/extraction.py`, `scoring.py`, `sentiment.py`, `scheduling.py`, `summary.py` | Sales intelligence + calendar |
| `routers/*.py` | REST endpoints |
| `security.py` | Admin key check, rate limiting |

### Agent pipeline
```mermaid
flowchart TD
  M["Customer message"] --> EX["Extract facts"] --> UP["update_customer_profile"] --> SE["analyze_sentiment"] --> PL{"Intent planner"}
  PL -- question --> KB["search_knowledge_base"]
  PL -- appointment --> SL["get_available_slots"]
  PL -- picks slot --> CF["ask to confirm"]
  PL -- yes --> BK["book_appointment(confirmed=true)"]
  KB --> CRM["update_crm_record + qualify_lead"]
  SL --> CRM
  CF --> CRM
  BK --> CRM
  CRM --> R{"found in KB?"}
  R -- no --> NF["'not in knowledge base'"]
  R -- yes --> W["LLM or template answer"]
```

**Design decision:** a rule-based planner chooses the tools and the LLM only writes text. Reasons: works without any API key, deterministic and unit-testable, the LLM can never trigger a booking by itself, and times/IDs in confirmations come straight from the database. Native LLM function calling can be added later because every tool already has a JSON-schema-like Pydantic input model.

### One voice turn
```mermaid
sequenceDiagram
  participant B as Browser
  participant A as FastAPI
  participant G as Agent
  participant K as RAG
  participant D as SQLite
  participant L as LLM
  B->>A: POST /messages {text}
  A->>G: handle(text)
  G->>D: profile + sentiment
  G->>K: search_knowledge_base
  K-->>G: chunks + score
  G->>D: qualify_lead
  G->>L: prompt with chunks (only if found and LLM configured)
  L-->>G: answer
  G->>D: save reply + sources
  A-->>B: reply, sources, lead, sentiment, tool trace
```

### Database
SQLite through SQLAlchemy ORM; see [DATABASE_DESIGN.md](DATABASE_DESIGN.md). Changing `DATABASE_URL` to PostgreSQL needs no code change except installing a driver.

### Integrations
| Integration | Status |
|---|---|
| Gemini API | Implemented, tested with mocked HTTP |
| Ollama | Implemented, tested with mocked HTTP |
| Google Calendar | Not implemented. `CalendarAdapter` protocol in `scheduling.py` is the seam |
| External CRM | Not implemented. CSV export available |

Production design: [SCALABILITY.md](SCALABILITY.md).
