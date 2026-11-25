# SalesPilot AI

An AI sales voice agent for **TechNova Academy** (a fictional training company). A prospective student talks to the agent by voice or text in English or Hindi. The agent answers from the company's own documents, remembers what the caller said, scores the lead, books a counselling slot, and writes a call summary. Sales staff see everything in a CRM and analytics dashboard.

> **Honest status:** runs fully offline and free in **demo mode** (no LLM: answers quote the knowledge base with clearly labelled templates). Add a free Gemini key or run Ollama locally to get LLM-written answers. See [What is real, tested, proposed](#what-is-real-tested-proposed).

## Quick start (Windows, PowerShell)

Requirements: **Python 3.11+**, **Node.js 20+**, **Chrome or Edge** (for voice).

```powershell
cd C:\path\to\SalesPilot-AI
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
| Agent orchestration with 10 validated, logged tools | `backend/app/agent/` |
| RAG: PDF/TXT upload, section chunking, BM25 (+ optional embeddings), source references, "not in KB" guard | `backend/app/services/rag.py` |
| Contextual + persistent memory, context window with rolling summary, inspect/delete memories | `orchestrator.py`, `customer_memories` table, CRM drawer |
| Lead extraction + transparent 0-100 scoring (HOT/WARM/COLD, reasons stored) | `services/extraction.py`, `services/scoring.py` |
| Sentiment (6 labels) + objections + recommended action | `services/sentiment.py` |
| Appointments: slots, confirm-before-book, double-booking prevention (app check + DB unique index), cancel, reschedule | `services/scheduling.py` |
| CRM: search, filter, sort, profile, transcripts, status, delete (cascade), CSV export | `routers/crm.py`, `pages/Crm.tsx` |
| Call summaries | `services/summary.py` |
| Analytics from real rows (empty states when no data) | `routers/analytics.py`, `pages/Analytics.tsx` |
| Settings: business profile, agent prompt, scoring weights, availability, voice, environment status | `routers/settings.py`, `pages/Settings.tsx` |

## Tests

```powershell
.\run-tests.ps1                         # 58 backend tests + frontend type-check/build
cd e2e; npm install; npm run verify-mcp # checks the 5 MCP servers
npm run workflow                        # 20-step browser workflow via Playwright MCP (fresh DB)
npm run audit                           # console/network/Lighthouse/perf via Chrome DevTools MCP
```

Latest results are recorded in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).

## MCP servers (free, open source)

Project-level configs (nothing global is touched): `.mcp.json` (Claude Code), `.vscode/mcp.json` (VS Code), `.cursor/mcp.json` (Cursor). Details and verification: [docs/MCP_SETUP.md](docs/MCP_SETUP.md).

## What is real, tested, proposed

| | Implemented | Tested here | Notes |
|---|---|---|---|
| Text conversation, RAG, memory, scoring, sentiment, booking, CRM, summaries, analytics | ✅ | ✅ pytest + browser | demo mode |
| Gemini / Ollama answers | ✅ | ✅ with mocked HTTP only | needs your key / Ollama to run for real |
| Embedding (hybrid) retrieval | ✅ | ⚠️ not with a live key | falls back to BM25 |
| Browser speech recognition | ✅ | ⚠️ UI + unsupported/blocked-mic paths only | headless test browser has no mic; test in Chrome/Edge |
| Docker compose | ✅ files | ❌ not built (no Docker daemon in build env) | |
| Google Calendar | ❌ adapter seam only | ❌ | local DB calendar is the real one |
| 100k-user architecture | 📄 design | ❌ | [docs/SCALABILITY.md](docs/SCALABILITY.md) |

## Project layout

```
backend/   FastAPI app (app/), sample knowledge base (data/knowledge), tests/
frontend/  React + TypeScript + Vite + Tailwind v4 + shadcn/ui-style components
e2e/       Browser verification through Playwright MCP + Chrome DevTools MCP, draw.io diagram export
docs/      Architecture, AI concepts, security, scalability, business model, interview prep, demo script
```
