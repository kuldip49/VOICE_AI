# SalesPilot AI — Project Report

**Report date:** 26 November 2026  
**Project status:** Functional MVP; Gemini configured and currently active in this workspace

## Executive summary

SalesPilot AI is a voice and text sales assistant for the fictional TechNova Academy. It answers prospective-student questions from the academy's knowledge base, gathers lead details, detects sentiment and objections, scores leads, offers counselling appointments, and records call summaries. Staff use the web dashboard to review leads, conversations, appointments, knowledge documents, and analytics.

The project is designed to run locally in demo mode without an LLM key. In the current workspace, `LLM_PROVIDER=gemini` and the configured model is `gemini-3.5-flash-lite`. The key is kept in the ignored local file `backend/.env`; its value is intentionally not recorded here.

## Product scope

The sample business profile, course catalog, policies, and FAQs are for TechNova Academy. The profile and agent instructions are editable in Settings, and staff can replace or add knowledge-base documents.

The main customer workflow is:

1. Start a text or voice conversation in English or Hindi.
2. Ask about courses, fees, schedules, policies, or other information in the knowledge base.
3. Share details such as name, interests, budget, and timeline; SalesPilot updates the customer and lead record.
4. Request a counselling appointment. The agent offers available slots and asks for explicit confirmation before booking.
5. End the conversation to save a summary and suggested follow-up action.
6. Review the lead, conversation, appointment, and analytics in the staff dashboard.

Sales operations include lead fact extraction, persistent customer memories, a transparent 0–100 lead score, six sentiment labels (`positive`, `neutral`, `negative`, `frustrated`, `interested`, `hesitant`), objection detection, appointment confirmation, and a structured call summary. Default score weights are intent 30, budget fit 20, urgency 20, product interest 15, and readiness 15; HOT starts at 70, WARM at 40, and both thresholds are configurable.

## Architecture and request flow

```text
Browser UI (React)
  ├─ Web Speech API: speech recognition and speech playback
  └─ JSON requests through the Vite /api proxy
       ↓
FastAPI backend
  ├─ Conversation API and deterministic agent planner
  ├─ Validated tools and audit logs
  ├─ Knowledge retrieval, extraction, sentiment, scoring, scheduling, summaries
  └─ Optional Gemini / Grok / Ollama text generation
       ↓
SQLite database
```

The agent follows a fixed, inspectable workflow: save the customer message; extract facts; analyze sentiment; detect intent; run the relevant tools; update and score the lead; then compose a response. The LLM writes grounded knowledge answers, but rule-based code controls actions such as appointment booking. Booking confirmations come from database results, and the agent does not book until the customer confirms.

The backend initializes tables and seeds sample knowledge documents at startup. The frontend uses lazy-loaded routes and sends requests to `/api`; the Vite dev server proxies those requests to FastAPI.

### Technology stack

- **Backend:** Python, FastAPI, Pydantic, SQLAlchemy, SQLite, pypdf, and httpx.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Radix-based UI components, Lucide icons, Recharts, and Sonner notifications.
- **Voice:** browser Web Speech API for speech recognition and speech synthesis.
- **Model providers:** Gemini and Grok REST APIs, local Ollama, and deterministic demo mode.
- **Verification tooling:** pytest for backend checks; Playwright MCP and Chrome DevTools MCP scripts under `e2e/` for browser workflows and audits.

## Application modules

### Frontend

The React 19, TypeScript, and Vite app includes:

- **Overview:** recent activity and headline metrics.
- **Live Agent:** text and voice conversations, transcript, sources, sentiment, lead score, and agent tool trace.
- **CRM:** lead search, filters, profiles, conversation history, saved memories, status updates, deletion, and CSV export.
- **Appointments:** slot list, booking, cancellation, and rescheduling.
- **Knowledge:** upload, inspect, search, and delete PDF, TXT, and Markdown documents.
- **Analytics:** lead, sentiment, question, objection, product, and appointment metrics.
- **Settings:** business profile, agent instructions, scoring weights, schedule, voice, provider status, and optional admin access.

Voice input uses the browser Web Speech API (`en-IN` and `hi-IN`); speech playback uses browser speech synthesis. Speech recognition availability and Hindi voices depend on the browser and device. In Chrome, recognition may use an internet speech service. Text input remains available as a fallback.

The Live Agent now recognizes spoken or typed end phrases such as “hang up,” “end the call,” and Hindi equivalents. It plays the farewell, ends the conversation, and saves its summary. This behavior is implemented, but live microphone behavior has not been verified on the user's PC.

### Backend

The FastAPI backend is organized around:

- `app/agent/orchestrator.py`: conversation pipeline, intent planning, response composition, and memory handling.
- `app/agent/tools.py`: validated agent tools and tool execution logging.
- `app/services/rag.py`: document extraction, chunking, BM25 retrieval, optional embedding blend, and relevance guard.
- `app/services/llm.py`: Gemini, Grok, Ollama, and demo provider implementations.
- `app/services/extraction.py`, `scoring.py`, `sentiment.py`, `scheduling.py`, and `summary.py`: sales intelligence and calendar behavior.
- `app/routers/`: conversation, CRM, appointment, knowledge, analytics, and settings endpoints.
- `app/models.py` and `app/database.py`: SQLAlchemy models and SQLite engine/session setup.

The ten agent tools are knowledge search, customer profile retrieval/update, lead qualification, sentiment analysis, slot lookup, booking, cancellation, conversation summary creation, and CRM record update.

### Data and persistence

The app uses SQLAlchemy with SQLite at `backend/data/salespilot.db` by default. The schema has 12 tables: customers, leads, conversations, messages, customer memories, appointments, knowledge documents, knowledge chunks, call summaries, sentiment records, agent tool logs, and app settings.

Foreign keys and cascade deletion support cleanup of a customer's related data. An active-slot unique index protects against double booking, including concurrent attempts. Existing schema changes are not managed by migrations; startup uses `create_all`.

The default local counselling calendar offers 30-minute slots Monday through Saturday from 10:00 to 18:00, with 60 minutes of minimum notice and a seven-day booking horizon. These values can be changed in Settings.

The current local database contains four sample knowledge documents and 24 knowledge chunks. Those existing chunks do not have stored embeddings, so current retrieval is BM25-based with query expansion. Gemini embeddings are available, and new document uploads can use them, but existing chunks have not been backfilled.

## AI and retrieval behavior

### Provider selection

The provider is selected from backend environment settings. Current local configuration explicitly selects Gemini and `gemini-3.5-flash-lite`; this avoids `auto` choosing another configured provider first. The model is listed in Google's [Gemini API model documentation](https://ai.google.dev/gemini-api/docs/models).

The API key stays on the backend. It is not embedded in the frontend or returned by Settings. The Live Agent shows which provider generated each answer.

### Grounded answers and Hindi retrieval

For a knowledge question, retrieval runs before answer generation. If a relevant source is found, Gemini writes the answer using that source context and the requested response language. If no source is found, the system gives a safe refusal rather than asking the model to guess. Greetings, acknowledgements, booking steps, and exact transactional messages may still use templates by design.

The screenshot's Hindi fee question previously missed the English course catalog because terms such as “कितना बजट लगेगा” were not mapped to price/fee vocabulary. The RAG pipeline now maps common Hindi price terms to English catalog terms and, when a Hindi query still has no match, may ask Gemini to translate it into English search terms. The final answer is still generated only if the knowledge base then returns a matching source.

The exact question from the screenshot was run through the agent against an in-memory database. It retrieved three source chunks and returned `generated_by=gemini:gemini-3.5-flash-lite` with a Hindi response. The live backend health endpoint and frontend API proxy also report Gemini as active.

## API surface

Customer-facing endpoints cover health, public settings, conversation creation, message exchange, conversation retrieval/end, and appointment-slot lookup. Staff endpoints cover conversation/tool logs; lead search, detail, update, delete, and CSV export; appointment management; knowledge upload/search; analytics; and settings.

FastAPI generates the interactive API reference at `/docs` when the backend is running.

## Security and operational boundaries

- `GEMINI_API_KEY` and other provider credentials belong in `backend/.env`, which is ignored by Git. Never paste secret values into reports, frontend code, screenshots, or commits.
- CRM and other admin routes require `X-Admin-Key` when `ADMIN_API_KEY` is configured. If that setting is empty, the admin routes are open; the MVP has no user accounts or role system.
- Public conversation endpoints have a per-process, in-memory rate limiter. A multi-worker deployment would need a shared limiter such as Redis.
- Uploads are limited by `MAX_UPLOAD_MB` (5 MB by default) and restricted to PDF, TXT, and Markdown.
- CORS origins are configurable. Error responses avoid returning stack traces.
- Audio is handled by browser speech features; SalesPilot does not upload recorded call audio to its backend.

## Running the project

For a standard Windows setup, the project documents:

```powershell
.\setup.ps1
.\start-all.ps1
```

The frontend is normally at `http://localhost:5173` and the backend at `http://127.0.0.1:8000`. In the current desktop session, ports 8000 and 8001 were already occupied by unrelated services, so SalesPilot was run with its backend on port 8002 and the Vite proxy pointed at that port. The current Live Agent URL is `http://127.0.0.1:5173/agent`.

## Verification status

### Verified during the recent Gemini/RAG work

- Gemini API key was detected without displaying its value.
- A live Gemini generation request succeeded.
- The exact Hindi fee question was retrieved from the sample knowledge base and answered by Gemini in an isolated in-memory agent run.
- The live backend health endpoint and frontend API proxy both reported `gemini:gemini-3.5-flash-lite`.

### Verification refresh on 26 November 2026

- Backend suite: **60 passed**.
- Frontend TypeScript check and production build: **passed**.
- Gemini generation and embedding requests: **passed** without exposing the API key.
- Hybrid retrieval: **passed** against a temporary in-memory SQLite knowledge base; the stored project database was not changed.
- Docker Compose configuration: **passed** `docker compose config --quiet`; an image build was not possible because Docker Desktop's engine was unavailable.

`PROJECT_PROGRESS.md` also records the earlier 20-step browser workflow and browser audit. That browser workflow was not rerun during this verification refresh.

### Not verified here

- Real microphone capture and Hindi speech recognition on the user's PC.
- End-to-end live voice use after the automatic hang-up change.
- Google Calendar API integration (the active calendar remains the local database).
- Docker image build in an environment with a working Docker engine.
- Load or deployment behavior at 100,000 users; the scalability document is a design, not a scale test.

## Known limitations and recommended next steps

1. Backfill embeddings for existing knowledge chunks if hybrid semantic retrieval is desired; current existing chunks are BM25-only.
2. Add focused automated coverage for Hindi query translation, grounded Gemini answers, provider failure fallback, and spoken hang-up behavior.
3. Add Alembic migrations and a PostgreSQL production configuration.
4. Replace the optional shared admin key with accounts, roles, and tenant isolation before multi-user deployment.
5. Implement Google Calendar and external CRM adapters if those integrations become requirements.
6. Consider streaming responses and server-side speech recognition if lower voice latency or wider browser support is needed.

## Key project references

- [README](../README.md)
- [System architecture](SYSTEM_ARCHITECTURE.md)
- [API reference](API.md)
- [Database design](DATABASE_DESIGN.md)
- [Security notes](SECURITY.md)
- [Project progress](../PROJECT_PROGRESS.md)

Other supporting documents in `docs/` cover the business model, AI concepts, scalability design, demo script, live-coding preparation, interview questions, and MCP setup.
