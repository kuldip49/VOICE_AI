# SalesPilot AI / Kiln & Signal - System Design As Built

**System design snapshot:** 26 November 2026  
**Scope:** Current repository implementation (`frontend/`, `backend/`, Docker configuration and supporting docs).

This document describes the system that exists in this repository. It distinguishes implemented behavior from optional provider configuration and future production plans. No credential values are included.

## 1. Product and system boundary

Kiln & Signal (repository/project name: SalesPilot AI) is a sales and admissions assistant for a configurable business profile. The sample profile and knowledge content describe TechNova Academy. Customers can ask questions in text or voice, share lead details, and request a counselling appointment. Staff use a web dashboard to review leads, conversations, appointments, knowledge content, analytics and settings.

The running application has a browser client, a Python API and agent, a local relational database, and optional external services. The browser's speech-recognition path and the inbound phone path are separate ways to get text into the same conversation agent.

## 2. Architecture diagram

See [`diagrams/system-design-as-built.mmd`](diagrams/system-design-as-built.mmd) for the editable Mermaid diagram. Solid paths are implemented. Dashed paths are optional or require external configuration. Future scale components are intentionally not represented as deployed services.

### Main components

| Layer | Implemented components | Responsibility |
|---|---|---|
| Browser UI | React 19, TypeScript, Vite; seven dashboard pages | Staff operations and the Live Agent experience |
| Browser voice | Web Speech API recognition and synthesis; microphone meter | Turns microphone speech into text in the browser and reads agent replies aloud; audio is not uploaded to this backend |
| HTTP edge | Vite `/api` proxy in development; Nginx reverse proxy in Docker | Same-origin API requests; forwards `/api/` to FastAPI |
| API | FastAPI, Pydantic validation, routers, startup hooks | Conversation, CRM, booking, knowledge, analytics, settings, telephony and health endpoints |
| Agent | Deterministic intent planner, ten validated tools, tool audit log | Extracts facts, analyzes sentiment, retrieves knowledge, qualifies leads, manages booking and composes replies |
| Services | BM25 RAG, optional embeddings, extraction, sentiment, scoring, scheduling, summaries, provider adapters | Reusable business and AI logic |
| Persistence | SQLAlchemy ORM and SQLite by default | Stores CRM, conversations, appointments, documents/chunks, audit data and settings |
| Optional providers | Gemini, Grok, Ollama; Exotel AgentStream; Sarvam realtime STT/TTS | Grounded answer writing / embeddings, local generation, inbound phone transport and speech when configured |

### Request routes

**Browser text or browser voice:** Browser UI -> same-origin `/api` -> FastAPI -> conversation router -> `SalesAgent` -> validated tools and services -> SQLite; a configured language model may write grounded knowledge answers. The reply, source list, lead/sentiment details and tool trace return to the UI.

**Inbound phone call:** Caller -> ExoPhone -> Exotel App Bazaar flow + Voicebot applet -> Basic Auth WSS `/api/telephony/exotel/stream` -> Sarvam realtime STT -> same `SalesAgent` and database -> Sarvam TTS PCM -> Exotel playback. Phone use needs an AgentStream-enabled Exotel account, a number assigned to that flow, public WSS hosting, Exotel credentials and a Sarvam key; code does not provision these.

**Development:** Vite listens on port 5173 and proxies `/api` to `http://127.0.0.1:8000`.  
**Docker Compose:** Nginx serves the frontend at port 8080 and proxies `/api/` to the backend service; a named Docker volume persists `/app/data`.

## 3. Conversation and agent flow

For each message, `backend/app/agent/orchestrator.py` uses a fixed, inspectable workflow:

1. Detect English/Hindi language and store the incoming message.
2. Extract volunteered facts such as name, interest, budget and timeline; update customer profile and persistent memory.
3. Analyze sentiment, confidence, objections and recommended action.
4. A rule-based planner selects intents and actions from the conversation state.
5. Run only validated, allow-listed tools for knowledge search, profile, qualification, booking, cancellation and summaries.
6. Recalculate a transparent 0-100 lead score and CRM category with reasons.
7. Compose the reply. Knowledge answers may use a configured LLM and retrieved context; otherwise a grounded template is used. Missing knowledge causes a safe refusal.
8. Append one qualifying question when useful and save the reply, sources, provider label and tool results.

The planner, not the LLM, controls actions. Booking requires explicit confirmation, and the exact slot and booking ID are taken from tool/database results. The database also enforces a partial unique index for active bookings at the same start time.

### Ten agent tools

`search_knowledge_base`; `retrieve_customer_profile`; `update_customer_profile`; `qualify_lead`; `analyze_sentiment`; `get_available_slots`; `book_appointment`; `cancel_appointment`; `create_conversation_summary`; `update_crm_record`.

Tool inputs use Pydantic schemas, execution is checked against an allow-list, and each invocation is recorded in `agent_tool_logs`.

## 4. Product modules and API areas

### Dashboard pages

| Route | Purpose |
|---|---|
| `/` | Overview metrics and recent activity |
| `/agent` | Text/voice conversation, transcript, source citations, sentiment, lead score and tool trace |
| `/crm` | Lead search/filter, customer profile, history/memories, status updates, deletion and CSV export |
| `/appointments` | Availability, booking, cancellation and rescheduling |
| `/knowledge` | Upload, inspect, search and delete PDF/TXT/Markdown documents |
| `/analytics` | Lead, sentiment, question, objection, product and appointment metrics |
| `/settings` | Business profile, prompts, score weights, schedule, voice, provider status and optional admin key |

### REST API domains

- **Health:** `GET /api/health`.
- **Conversations:** create conversation; post messages; fetch/end conversation; inspect conversations and tool logs (admin).
- **CRM:** list/export leads; retrieve and update lead; delete customer/lead; remove individual memories.
- **Appointments:** public slot lookup; staff list/create/cancel/reschedule.
- **Knowledge:** list documents/chunks; upload/delete documents; search.
- **Analytics:** overview aggregates.
- **Settings:** public settings; staff read/update configuration.
- **Telephony:** Exotel readiness status and authenticated bidirectional WebSocket stream; call audio is bridged to Sarvam speech services and the shared conversation agent.

FastAPI exposes interactive OpenAPI documentation at `/docs` while the backend is running. Pydantic request models validate HTTP inputs and agent-tool arguments.

## 5. Data model

The SQLAlchemy source currently defines **13 ORM tables** in `backend/app/models.py` (the earlier architecture note saying 12 predates the telephony call table):

| Table | Purpose |
|---|---|
| `customers` | Contact and language profile |
| `leads` | Interest, budget, timeline, qualification, score and status; one lead per customer |
| `conversations` | Channel, language, state and rolling memory summary |
| `messages` | User/assistant transcript, intent, source and generation metadata |
| `customer_memories` | Key/value facts retained across conversations |
| `appointments` | Local-calendar slots, booking state and topic |
| `knowledge_documents` | Uploaded source file metadata/status |
| `knowledge_chunks` | Searchable document sections and optional embedding JSON |
| `call_summaries` | Summary, objections, interests, sentiment and follow-up |
| `telephony_calls` | Exotel call SID, conversation link, caller and call state |
| `sentiment_records` | Per-message sentiment and recommended action |
| `agent_tool_logs` | Tool input/output, success/error and duration |
| `app_settings` | Business profile, prompts, score weights, schedule and voice settings |

Important relationships: customer -> lead (one-to-one), conversations, memories and appointments; conversation -> messages, summary, sentiment/tool logs; knowledge document -> chunks; Exotel call -> conversation. Customer/document/conversation deletion uses cascading relationships where configured. Active appointment uniqueness is enforced at the database index.

**Default storage:** `backend/data/salespilot.db` (SQLite). SQLite foreign keys and WAL are enabled. `DATABASE_URL` can point SQLAlchemy at another compatible database, but migrations and production PostgreSQL operations are not included in the MVP.

## 6. Technology inventory

### Frontend

| Technology | Use |
|---|---|
| React 19 | UI component runtime and page composition |
| TypeScript | Typed application, API models and hooks |
| Vite 8 | Development server, `/api` proxy and production build |
| React Router 7 | Application routes and lazy page loading |
| Tailwind CSS 4 | Styling and shared CSS design tokens |
| Radix UI + class-variance-authority | Accessible UI primitives and variants (shadcn/ui-style source components) |
| Lucide React | Icons |
| Recharts 3 | Dashboard charts |
| Sonner | Toast notifications |
| Browser Web Speech API | SpeechRecognition for STT; `speechSynthesis` for TTS |

### Backend and data

| Technology | Use |
|---|---|
| Python 3.12 container (Python 3.11+ project baseline) | Backend runtime |
| FastAPI + Uvicorn | REST API and ASGI server |
| websockets 15 | Async client connections to Sarvam realtime STT and streaming TTS |
| Pydantic 2 + pydantic-settings | Request/tool validation and environment configuration |
| SQLAlchemy 2 | ORM and database-independent query layer |
| SQLite | Default zero-service local database |
| httpx | HTTP requests to model APIs; mockable in provider tests |
| pypdf | PDF knowledge-file text extraction |
| pytest + FastAPI TestClient | Backend unit/API test suite |
| Playwright MCP / Chrome DevTools MCP scripts | Browser workflow and UI audit tools in `e2e/` |

### Telephony and speech providers

| Provider | Use |
|---|---|
| Exotel AgentStream | Indian inbound phone number and bidirectional WSS audio transport; account entitlement and Voicebot flow assignment are required |
| Sarvam realtime STT/TTS | Live English/Hindi transcripts and 16 kHz mono linear16 spoken audio for phone calls; a Sarvam key is required |

### AI and retrieval

| Technology | Status and role |
|---|---|
| Deterministic planner and templates | Core behavior; works without an LLM key and controls transactional actions |
| Gemini REST | Configurable answer generation and embeddings; current local `.env` selects Gemini (`gemini-3.5-flash-lite`) according to the project status report |
| Grok REST | Provider adapter is implemented and configurable |
| Ollama | Local provider adapter is implemented and configurable |
| Demo provider | Grounded template fallback when no external provider is selected/available |
| BM25 | Default keyword retrieval; explainable and can run offline |
| Gemini embeddings | Optional hybrid retrieval; chunks can store embeddings, but existing sample chunks may remain BM25-only until backfilled |

The model credentials are backend-only environment values and are deliberately excluded from this document. Provider configuration is in `backend/app/config.py`; generation and provider selection are in `backend/app/services/llm.py`.

## 7. Configuration, security and deployment

### Configuration

Environment settings include `DATABASE_URL`; `LLM_PROVIDER` (`auto`, `grok`, `gemini`, `ollama`, `demo`); provider API keys/model names; Ollama URL; Exotel account SID/key/token, number and public WSS URL; Sarvam key/models/voices; `ADMIN_API_KEY`; CORS origins; upload size; rate limit and timezone. Defaults and names are defined in `backend/app/config.py`. Secrets belong in the ignored `backend/.env`, never in frontend code or generated documentation.

### Implemented security controls

- Optional shared `X-Admin-Key` protects staff endpoints when `ADMIN_API_KEY` is set; there are no user accounts or roles.
- Pydantic validation for API and tool input; strict ten-tool allow-list with no arbitrary shell, SQL or code execution path.
- SQLAlchemy parameterized ORM operations; limited CORS; generic client errors; per-process in-memory rate limit on conversation endpoints.
- File type/size checks, sanitized names and PDF signature validation for knowledge uploads.
- Appointment confirmation plus database-level active-slot uniqueness.
- UUID conversation IDs, cascade deletion and individual memory deletion.
- Browser voice audio is not sent to this backend; recognized text is stored. Browser speech recognition can send audio to the browser vendor's speech service.
- The Exotel WSS handshake validates HTTP Basic Auth against the configured API key/token. LLM mode sends message/context to the selected LLM provider; live phone audio is sent to Sarvam when configured.

### Operational topology

Local scripts: `setup.ps1`, `start-all.ps1` (or separate frontend/backend launch scripts). Docker Compose builds the Python API and static React/Nginx frontend, exposes port 8080 and persists backend data in the `salespilot-data` volume. No managed cloud deployment is defined here.

## 8. Implemented scope versus future work

### Present in the codebase

English/Hindi text conversation; browser voice UI; inbound Exotel AgentStream and Sarvam speech bridge (external phone setup required); grounded document Q&A and source tracking; lead extraction/scoring; sentiment and objections; CRM; appointment lifecycle; call summaries; analytics; settings; CSV export; dashboard; SQLite persistence; Docker Compose configuration.

### Not currently a deployed or completed integration

Google Calendar (the active calendar is database-backed and has an adapter seam); external CRM sync (CSV export exists); production accounts/roles and multi-tenancy; PostgreSQL migrations; Redis/distributed limiting; background workers; Kubernetes/cloud deployment; CI/CD and load-tested scale. These belong to documented future plans, not the current runtime architecture.

### Verification record in the repository

`PROJECT_PROGRESS.md` reports (26 November 2026) 60 backend tests passing, frontend TypeScript/production build passing, lint passing with five warnings, and a successful live Gemini smoke check. It records Docker Compose configuration as checked but Docker image build unavailable, and microphone/live phone/browser refresh checks as not completed in that verification session. The Exotel/Sarvam change in this snapshot has not been connected to a live account or number, and no tests were rerun while generating this design PDF.

## 9. Source map

| Concern | Main source files |
|---|---|
| Frontend routing/UI | `frontend/src/App.tsx`, `frontend/src/pages/`, `frontend/src/components/` |
| Browser voice and HTTP client | `frontend/src/hooks/useVoice.ts`, `frontend/src/lib/api.ts` |
| API startup/config | `backend/app/main.py`, `backend/app/config.py`, `backend/app/security.py` |
| Agent and tools | `backend/app/agent/orchestrator.py`, `backend/app/agent/tools.py` |
| RAG and LLM | `backend/app/services/rag.py`, `backend/app/services/llm.py` |
| Business services | `backend/app/services/` |
| Persistence | `backend/app/models.py`, `backend/app/database.py`, `backend/app/seed.py` |
| HTTP API | `backend/app/routers/` |
| Runtime packaging | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` |
| Tests / browser automation | `backend/tests/`, `e2e/` |
| Security / run notes | `docs/SECURITY.md`, `README.md`, `docs/TELEPHONY_SETUP.md` |

