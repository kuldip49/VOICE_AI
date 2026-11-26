# Kiln & Signal

A considered workspace for customer conversations, lead follow-through and counselling appointments. The demo is configured for fictional **TechNova Academy**; its sample knowledge, policies and dashboard data can be replaced for another business.

> **Honest status:** the project runs offline in demo mode when no model is configured. This workspace has Gemini configured locally; public clones must add their own key in `backend/.env` to get model-written answers. See [project status and verification](#project-status-and-verification).

## Quick start (Windows, PowerShell)

Requirements: **Python 3.11+**, **Node.js 20+**, **Chrome or Edge** (for voice).

```powershell
cd C:\path\to\VOICE_AI
powershell -ExecutionPolicy Bypass -File .\setup.ps1      # venv, pip install, .env, database, npm install
powershell -ExecutionPolicy Bypass -File .\start-all.ps1  # backend :8000 + frontend :5173, opens the browser
```

Or step by step:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
cd backend; ..\.venv\Scripts\python.exe -m app.seed; cd ..
cd frontend; npm install; cd ..
.\start-backend.ps1     # terminal 1  -> http://127.0.0.1:8000/docs (API docs)
.\start-frontend.ps1    # terminal 2  -> http://localhost:5173
```

Open **http://localhost:5173/agent**, click **Start call**, allow the microphone, and talk.

### Optional: connect an actual phone number

Inbound calls use Exotel AgentStream and the same sales agent, with Sarvam realtime speech recognition and speech output. Configure Exotel credentials, an ExoPhone, a public WSS endpoint, and a Sarvam key in `backend/.env`; then run `python -m app.telephony_setup` from `backend/` for the Exotel console steps. In Exotel, assign the number to an App Bazaar flow with a Voicebot applet. The Settings page shows which values are present. Callers can speak English or Hindi and press 9 to switch languages. Follow [Inbound phone calls](docs/TELEPHONY_SETUP.md) for setup and trial/account limits. Exotel AgentStream and Sarvam usage may incur charges; code alone does not provision a phone number.

### Turn on a real LLM (optional, free options)

| Option | How | Cost |
|---|---|---|
| Grok | Get a key at https://console.x.ai/, set `GROK_API_KEY=` in `backend\.env`, keep `LLM_PROVIDER=auto`, restart backend | xAI API pricing |
| Gemini | Get a key at https://aistudio.google.com/apikey, set `GEMINI_API_KEY=` in `backend\.env`, restart backend | Free tier with limits |
| Ollama (local) | Install from https://ollama.com, run `ollama pull llama3.2`, keep `LLM_PROVIDER=auto` | Free, runs on your PC |

The badge in the top bar shows which mode is active. Every assistant message stores `generated_by` (`demo-rules`, `grok:…`, `gemini:…`, `ollama:…`, or `demo-rules (llm-error)` if the model failed).

## Demo script (2 minutes)

1. **Live agent** → Start call → *"Hello, I want to learn AI and machine learning. Can you tell me about your courses?"* → answer cites `course_catalog.txt`.
2. *"My name is Rahul"* → *"My budget is around 20,000"* → *"I want to start next month"* → the Caller and Lead score panels fill in with reasons.
3. *"That's too expensive for me"* → sentiment **hesitant**, objection **price**, agent answers with EMI / discount policy.
4. *"Do you offer a blockchain course?"* → *"not in our knowledge base"* (no guessing).
5. *"Can I book a counselling appointment?"* → *"2"* → *"yes"* → booked. Nothing is saved before the "yes".
6. **End call** → summary + next step. Open **Leads**, **Appointments**, **Analytics**.
7. Switch language to **हिन्दी** and ask *"रिफंड की नीति क्या है?"*

Full 5-minute script: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Features

| Module | Where |
|---|---|
| Voice conversation (Web Speech STT/TTS, mic level meter, hands-free, barge-in, mute, stop speaking, text fallback) | `frontend/src/pages/LiveAgent.tsx`, `frontend/src/hooks/useVoice.ts` |
| Consented browser call recordings with caller name/time and private manager playback | `frontend/src/pages/LiveAgent.tsx`, `frontend/src/pages/CallRecordings.tsx`, `backend/app/routers/recordings.py` |
| Inbound telephone calls (Exotel AgentStream WebSocket, Basic Auth, Sarvam live Hindi/English speech, sales agent, CRM and summaries) | `backend/app/routers/telephony.py`, `backend/app/services/exotel_stream.py`, [setup guide](docs/TELEPHONY_SETUP.md) |
| Agent orchestration with 10 validated, logged tools | `backend/app/agent/` |
| RAG: PDF/TXT upload, section chunking, BM25 (+ optional embeddings), source references, "not in KB" guard | `backend/app/services/rag.py` |
| Contextual + persistent memory, context window with rolling summary, inspect/delete memories | `orchestrator.py`, `customer_memories` table, CRM drawer |
| Lead extraction + transparent 0-100 scoring (HOT/WARM/COLD, reasons stored) | `services/extraction.py`, `services/scoring.py` |
| Sentiment (6 labels) + objections + recommended action | `services/sentiment.py` |
| Appointments: slots, confirm-before-book, double-booking prevention (app check + DB unique index), cancel, reschedule | `services/scheduling.py` |
| CRM: search, filter, sort, profile, transcripts, status, delete (cascade), CSV export, and an evidence-grounded Lead Rescue Brief with a copyable follow-up draft | `routers/crm.py`, `services/lead_rescue.py`, `pages/Crm.tsx` |
| Call summaries | `services/summary.py` |
| Analytics from real rows (empty states when no data) | `routers/analytics.py`, `pages/Analytics.tsx` |
| Settings: business profile, agent prompt, scoring weights, availability, voice, environment status | `routers/settings.py`, `pages/Settings.tsx` |
| Monochrome client desk with editorial type, restrained ambient motion and reduced-motion support | `frontend/src/index.css`, `components/layout/AppShell.tsx` |

## Tests

```powershell
.\run-tests.ps1                         # backend tests + frontend type-check/build
cd e2e; npm install; npm run verify-mcp # checks the 5 MCP servers
npm run workflow                        # 20-step browser workflow via Playwright MCP (fresh DB)
npm run audit                           # console/network/Lighthouse/perf via Chrome DevTools MCP
```

Latest results are recorded in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).

## MCP servers (free, open source)

Project-level configs (nothing global is touched): `.mcp.json` (Claude Code), `.vscode/mcp.json` (VS Code), `.cursor/mcp.json` (Cursor). Details and verification: [docs/MCP_SETUP.md](docs/MCP_SETUP.md).

## Project status and verification

Every row below has a green check for a contribution that is present and evidence that was checked. A check may mean an implemented feature, validated configuration, or documented design. The notes spell out boundaries: a green check does not claim that an optional external service, physical microphone, container image build, or production-scale deployment was verified.

| Area | In the project | Evidence checked | Scope and current limits |
|---|---|---|---|
| Text sales workflow: RAG, memory, scoring, sentiment, booking, CRM, summaries, analytics | ✅ Implemented | ✅ 60 backend tests pass; the 20-step browser workflow is recorded in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) | Demo mode remains available when no model key is configured. |
| Kiln & Signal visual identity and monochrome interface | ✅ Implemented | ✅ TypeScript/Vite production build passes; lint has five recorded warnings | The native browser screenshot audit was unavailable in this Windows session; reduced-motion support is included. |
| Gemini / Ollama answers | ✅ Both provider adapters are implemented | ✅ Gemini generation checked live; provider HTTP behavior is covered by mocked tests | Ollama was not run as a local service here. Gemini keys are local and are not in GitHub. |
| Embedding hybrid retrieval | ✅ Optional hybrid ranking is implemented | ✅ Live Gemini embedding and hybrid retrieval checked against an in-memory knowledge base | Existing chunks without vectors use BM25 until embeddings are generated for them. |
| Browser speech recognition and playback | ✅ Uses browser Web Speech APIs | ✅ Frontend production build passes; unsupported and blocked-microphone UI paths are covered by the recorded browser checks | A live microphone conversation still needs a Chrome/Edge check on the target device. |
| Exotel inbound phone assistant | ✅ WebSocket bridge and Sarvam speech integration are implemented | ⚠️ External phone call not configured here | An Exotel AgentStream-enabled account, ExoPhone assigned to a Voicebot flow, public WSS host, Exotel credentials and Sarvam key are required. AgentStream may be separately priced. See [setup guide](docs/TELEPHONY_SETUP.md). |
| Docker Compose | ✅ Compose and container files are included | ✅ `docker compose config --quiet` passes | Image build was not run because Docker Desktop's engine was unavailable in this session. |
| Local appointment calendar and provider seam | ✅ Local database calendar and adapter interface are implemented | ✅ Appointment booking tests pass in the backend suite | A Google Calendar API adapter is future work; local database scheduling is active. |
| 100,000-user architecture | ✅ A scaling design and roadmap are documented in [docs/SCALABILITY.md](docs/SCALABILITY.md) | ✅ Design assumptions and implementation boundaries are documented | Design only: no 100,000-user load test or production deployment is claimed. |

## Project layout

```
backend/   FastAPI app (app/), sample knowledge base (data/knowledge), tests/
frontend/  React + TypeScript + Vite + Tailwind v4 + shadcn/ui-style components
e2e/       Browser verification through Playwright MCP + Chrome DevTools MCP, draw.io diagram export
docs/      Architecture, AI concepts, security, scalability, business model, interview prep, demo script
```
